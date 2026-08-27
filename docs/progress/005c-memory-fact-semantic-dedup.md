# 过程记录 005c：记忆存储范式重构与语义去重（三期优化）

## 1. 状态

| 字段 | 值 |
|---|---|
| 对应 Spec | [SPEC-005](../../specs/005-memory-system/spec.md)（记忆系统三期增强） |
| 前置记录 | [005b-memory-evolution-consolidation](./005b-memory-evolution-consolidation.md) |
| 当前阶段 | 自然语言 fact 范式 + 语义去重 + 主动记忆调和，线上验证完成 |
| 最后更新 | 2026-08-27 |

## 2. 背景与问题

二期的演化链 + 整合解决了「记忆怎么变、怎么整理」，但线上实测暴露出更底层的三个问题：

1. **三元组抽取脆弱**：`subject/predicate/value` 强制 LLM 做语义解析，极易产出畸形结果，例如「用户 喜欢吃 用户 不喜欢吃 辣」（自我引用）、「用户 喜欢 不吃辣」（否定错位）。无论怎么强化 prompt、归一化谓词，都无法 100% 杜绝结构化解析错误。
2. **主动/自动提取重复**：`memory.add`（主动）与 `flush`（自动）两条独立写入路径，各自抽一遍同一句话，字段略有差异就各写一条，产生重复记忆。
3. **正反偏好无法演化**：「喜欢吃辣」→「不喜欢吃辣」语义相反但 `conflict_key`（基于字段哈希）对不上，两条并存，无法更新。

## 3. 本次完成

### 3.1 存储范式：从「三元组」到「自然语言 fact」

- `ExtractedCandidate` / `MemoryCandidatePayload` / `AddMemoryInput` 新增 `fact`（自然语言事实陈述）作为主字段，`subject/predicate/value` 降级为可选（默认空）。
- 抽取 prompt 改为**只输出一句通顺的 fact**（如「用户不喜欢吃辣」），不再要求拆分字段。
- `content` 直接使用 fact，渲染自然（不再有「喜欢 不吃辣」的怪异拼接）。
- `memory.add` 工具的 `AddMemoryInput` **彻底移除** `subject/predicate/value/negated`，只保留 `fact`，从源头杜绝 LLM 去填结构化字段。

### 3.2 语义去重（写入时 + 定期）

新增 `memory/dedup.py`：

- `fact_similarity(a, b)`：对称词法相似度（jieba），并含**否定极性判断**——「喜欢」vs「不喜欢」极性相反，直接判不相似（0.0），防止正反偏好被误合并。
- 阈值 `DEDUP_THRESHOLD = 0.80`，保守倾向（宁漏勿错删）。

写入时去重（`flush.py`）：自动提取每个 candidate 前，先查该用户 active 记忆，`fact_similarity` 命中就跳过，不重复写。

定期去重（`consolidate.py`）：整合任务增加确定性去重阶段（Phase 1，无需 LLM），词法相似度 ≥ 阈值就 supersede 旧的。

### 3.3 主动记忆语义调和（reconcile）

新增 `memory/reconcile.py`，实现「模型提议 + 工程裁决」：

- 每次主动记忆（`memory.add`）时，把新 fact + 现有相关记忆（词法粗筛 top 5）喂给模型。
- 模型输出四选一决策：`add`（新增）/ `update`（更新旧值）/ `supersede`（正反取代）/ `ignore`（重复忽略）。
- 工程层裁决：校验 `target_id` 必须真实存在且属于该用户，否则回退为 `add`，杜绝模型幻觉误删。

## 4. 关键决策

### 4.1 为什么选词法相似度而非 embedding

去重场景用词法（jieba）而非 embedding，理由：

- 词法本地计算、无外部服务依赖，flush/consolidate 路径此前一直没接 embedding，直接接会增加失败点。
- 对「喜欢吃辣」vs「喜欢吃辣的食物」这类高重叠文本，词法已够用；真正需要区分的是「否定极性」，用否定标记词表解决。

### 4.2 否定极性判断（关键）

纯词法相似度无法区分「喜欢吃辣」（同义）和「不喜欢吃辣」（反义）——两者 token 重叠度几乎一样。因此 `fact_similarity` 增加极性判断：一方含否定词（不/没/无/别/非/否认/拒绝）而另一方不含，直接判 0.0。这是去重正确性的核心。

### 4.3 reconcile 的粗筛必须「不排除正反」

去重的 `fact_similarity` 会排除正反（返回 0），但 reconcile 恰恰**需要**正反候选进入模型判断（让模型决定 supersede）。因此 reconcile 的粗筛改用**纯词法相似度**（不排除正反），与去重逻辑区分开。

### 4.4 模型提议 + 工程裁决（贯穿原则）

与一期、二期一脉相承：reconcile 中模型只输出决策提议，工程层对 `target_id` 做确定性校验后才执行。宁可回退 `add`，也不让幻觉 id 破坏数据。

## 5. 文件变更

新增：

- `apps/api/src/zhiban/memory/dedup.py`（语义相似度 + 否定极性 + 阈值）
- `apps/api/src/zhiban/memory/reconcile.py`（主动记忆语义调和）

修改：

- `apps/api/src/zhiban/memory/extractor.py`（抽取改输出 fact，移除结构化字段要求）
- `apps/api/src/zhiban/memory/schemas.py`（payload/view/request 加 fact，结构化字段可选）
- `apps/api/src/zhiban/memory/service.py`（`_render_content` 优先 fact；fingerprint/conflict_key 基于 fact）
- `apps/api/src/zhiban/memory/ids.py`（新增 `fact_fingerprint` / `fact_conflict_key`）
- `apps/api/src/zhiban/memory/flush.py`（写入时语义去重 + 补 negated + 补 fact）
- `apps/api/src/zhiban/memory/consolidate.py`（增加确定性去重 Phase 1）
- `apps/api/src/zhiban/memory/tools.py`（`MemoryAddTool` 移除结构化字段、接入 reconcile）
- `apps/api/src/zhiban/memory/router.py`（create API 改用 fact）
- `apps/api/src/zhiban/agent/subagents/memory_agent.py`（把 llm 传给 MemoryAddTool）

## 6. 验证摘要

### 6.1 抽取稳定性

```
输入「记住我不吃辣」→ fact="用户不喜欢吃辣"（自然语句，无畸形）
输入「我喜欢喝咖啡」→ fact="用户喜欢喝咖啡"
```

### 6.2 语义去重

```
fact_similarity 阈值 0.80：
  喜欢吃辣 vs 喜欢吃辣的食物 -> 0.800 去重 ✅
  喜欢吃辣 vs 不喜欢吃辣     -> 0.000 保留 ✅（正反不误判）
  喜欢喝咖啡 vs 喜欢喝咖啡   -> 1.000 去重 ✅
  住在北京 vs 住在上海       -> 0.667 保留 ✅
```

### 6.3 写入时去重（端到端）

```
[1] 主动记忆「用户喜欢吃辣」-> add
[2] flush 提取「用户喜欢吃辣的食物」-> 语义去重命中，跳过
[3] flush 提取「用户不喜欢吃辣」-> 正反不误判（未命中）
最终：只有 1 条「吃辣」active 记忆
```

### 6.4 reconcile 四动作

```
[1] 重复「喜欢吃香菜」-> ignore ✅
[2] 补充「非常喜欢吃香菜」-> update ✅
[3] 反转「不喜欢吃香菜」-> supersede ✅
[4] 全新「住在北京」-> add ✅
```

## 7. 已知问题与局限

1. **词法相似度对近义但不重叠的表达无力**：「我喜欢辣」vs「我爱辣」词法重叠低，可能漏去重。需要 embedding 才能根治，属后续优化。
2. **reconcile 只作用于主动记忆**：自动提取（flush）仍用规则去重，未用模型判断（成本考虑）。若自动提取也需正反演化，需扩展。
3. **negated 字段与 fact 并存**：二期引入的 `negated` 字段在 fact 范式下已无必要（否定直接写在 fact 里），但为兼容保留，未清理。
4. **本地自动化测试未跑**：本机 Docker/依赖环境问题，仅线上端到端验证。

## 8. 下一步

1. **embedding 语义去重**：用 bge-m3 embedding 替代词法，处理「喜欢」vs「爱」这类近义不重叠的表达。
2. **自动提取也走 reconcile**：flush 抽取后同样用模型判断（成本可控时）。
3. **清理 negated 冗余字段**：确认 fact 范式稳定后，移除 `negated` 及结构化字段的写入逻辑。
4. 补齐本地/CI 自动化回归测试。
