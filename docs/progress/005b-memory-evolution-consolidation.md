# 过程记录 005b：记忆自我整合与演化（二期优化）

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-005](../../specs/005-memory-system/spec.md)（记忆系统二期增强） |
| 前置记录 | [005-memory-system](./005-memory-system.md) |
| 当前阶段 | 记忆演化链 + 记忆整合任务实现与线上验证完成 |
| 最后更新 | 2026-08-27 |

## 2. 背景与目标

SPEC-005 一期实现了「候选提取 → 校验 → 决策（add/update/ignore）→ 混合检索 → 治理」的完整闭环，但存在两个深层次缺口：

1. **冲突更新是「断头」的**：`_decide` 判定为 `update` 后，`process_candidate` 的 update 分支只标记了 record，没有真正执行更新——旧记忆既没被 supersede，新值也没落库。记忆的「演化」链路是断的。
2. **无「整合」层**：记忆是零散的三元组快照，没有低频的梳理——同一个人/事的记忆不会合并、矛盾不会显式处理、冗余不会清除。

对照小 Q（qmemory_runtime）的记忆策略：小 Q 因 C2C 关系型记忆做了大量「防出错」取舍（alias 双证据、relation 白名单、recent_status 本人确认、A→B/B→A 双向画像等）。而知伴面向单用户「自我记忆沉淀」，无 C2C 社交记忆需求，场景更简单，因此可以在「整合与演化」上做得更自由、更有深度。

本次二期优化的核心约束与一期一致：**LLM 只生成「提议」，确定性代码负责校验、裁决、持久化**。

## 3. 本次完成

### 3.1 记忆演化链（补全冲突更新）

- `_decide` 由返回 `str` 改为返回 `(decision, supersede_target)`；槽位冲突时返回要 supersede 的旧记忆（取 `updated_at` 最新的一条）。
- `process_candidate` 的 update 分支真正落地：新值以 `active` 落库，旧记忆标记 `status=superseded` 并通过 `superseded_by_id` 指向新记忆。
- 效果：用户「吃辣」→「不吃辣」的偏好演变被完整保留，支持「你之前……现在……」的时间演化追问。

### 3.2 记忆整合任务（memory.consolidate）

- 新增 `memory/consolidate.py`：加载用户全部 active 记忆 → LLM 识别冗余（语义重复）与矛盾（同槽位值相反）→ 输出「保留谁、淘汰谁」的结构化提案 → 工程层确定性 apply（校验 id 真实存在且属于该用户，再标记 superseded）。
- 新增 worker handler `handle_memory_consolidate`，注册 `memory.consolidate` job。
- 新增 `memory.consolidate` 工具，挂载到记忆子代理（MemoryAgent）。

### 3.3 双触发机制

- **自动触发**：每轮 `memory.extract` 完成后，若该用户 active 记忆数 ≥ 15（`DEFAULT_CONSOLIDATE_THRESHOLD`），自动入队 `memory.consolidate`。幂等键 `memconsolidate:{user_id}` 保证同一用户不堆积重复任务。
- **主动触发**：用户说「整理一下我的记忆」，记忆子代理调用 `memory.consolidate` 工具入队。

## 4. 关键决策

### 4.1 LLM 提议 + 工程裁决

整合任务中，LLM 只输出「哪条记忆被哪条取代」的提案（supersede 对），**不直接改库、不新造内容**。工程层对每个提案做确定性校验：`superseded_id` 与 `kept_id` 必须是该用户真实的 active 记忆、且不为同一条，才执行 supersede。避免 LLM 幻觉引入脏数据。

### 4.2 复用演化链机制，不新增 schema

整合的落地完全复用一期已有的 `status=superseded` + `superseded_by_id` 字段，不引入新表、新迁移。整合与「冲突更新」共享同一条演化链语义。

### 4.3 主动触发走异步 job，不阻塞对话

用户主动「整理记忆」时，工具只入队 job 并返回「已开始整理」，由 worker 异步完成。与自动触发共用同一执行路径，交互即时、逻辑统一。

### 4.4 阈值与宁缺毋滥

- 自动触发阈值默认 15 条（记忆过少时整合收益低、还费 LLM 调用）。
- 整合提示词要求「不确定就留空数组」，宁可不整合也不错整合。

## 5. 文件变更

新增：

- `apps/api/src/zhiban/memory/consolidate.py`（整合核心 + 阈值常量 + active 计数）
- `scripts/verify_memory_evolution.py`（演化链线上验证脚本）
- `scripts/verify_memory_consolidate.py`（整合线上验证脚本）

修改：

- `apps/api/src/zhiban/memory/service.py`（`_decide` 返回元组；update 分支真正落地演化链）
- `apps/api/src/zhiban/workers/memory_jobs.py`（新增 `handle_memory_consolidate` + 自动触发）
- `apps/api/src/zhiban/workers/main.py`（注册 `memory.consolidate`）
- `apps/api/src/zhiban/memory/tools.py`（新增 `MemoryConsolidateTool`）
- `apps/api/src/zhiban/agent/subagents/memory_agent.py`（注册工具 + 提示词支持「整理记忆」）
- `apps/api/tests/test_memory_service.py`（扩展槽位冲突测试，断言演化链）

## 6. 验证摘要

### 6.1 演化链（线上端到端）

```
[1] 第一次写入 decision=add
[2] 第二次写入（同 slot 不同值）decision=update
[3] active 记忆数=1（旧值不再 active）
记录: value='吃辣' status=superseded superseded_by=-> a473f9a0（指向新记忆）
```

### 6.2 整合任务（线上端到端）

构造 6 条记忆（3 组矛盾/冗余），触发整合：

```
[1] 整合前 active 记忆数 = 6
[2] 整合结果 superseded = 3
[3] 整合后 active = 3，superseded = 3
保留 active：住在 上海 / 喜欢 不吃辣 / 喜欢 咖啡
被 supersede：住在 北京 → / 喜欢 喝咖啡 → / 喜欢 吃辣 →（各自指向保留记忆）
```

矛盾（吃辣 vs 不吃辣、住北京 vs 住上海）与冗余（咖啡 vs 喝咖啡）均被正确消解。

### 6.3 质量门禁

- lint（ruff）无错误。
- `python -m py_compile` 全部通过。
- 未在本地跑集成测试（本机 Docker Desktop 未启动、磁盘接近满）；线上真实环境端到端验证替代。

## 7. 已知问题与局限

1. **整合是「保留/淘汰」而非「重写合并」**：当前整合只做 supersede（保留最新一条、淘汰冗余/旧值），不做把多条记忆「重写」成一条更凝练的新记忆。这是刻意取舍——重写需新增记忆、有幻觉风险，收益待评估。
2. **演化历史暂未暴露给检索**：`superseded` 记忆不进入检索（符合 SPEC-MEM-004），但 Agent 回答时还看不到「这条记忆曾有旧值」的演化历史。要支持「你之前……现在……」的主动追问，需在检索注入时附带演化链（下一步）。
3. **本地测试未跑**：因本机 Docker/磁盘问题，演化链与整合的自动化测试未在本地 pytest 全量回归，仅线上端到端验证。`test_memory_service.py` 的演化链断言需在 CI/本地环境补齐回归。
4. **整合阈值 15 是经验值**：未做数据驱动的阈值调优。

## 8. 下一步

1. **演化历史检索暴露**：检索注入时附带 `superseded_by` 链，让 Agent 能回答「你之前喜欢 X，现在喜欢 Y」。
2. **整合「重写合并」**：在 supersede 基础上，支持把语义相近的多条记忆合并重写为一条更凝练的新记忆（需审慎评估幻觉风险）。
3. **阈值与整合频次的评测**：建立评测集，量化整合的准确率（是否误淘汰）。
4. 补齐本地/CI 自动化回归测试。
