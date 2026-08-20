# SPEC-005：记忆系统（候选、校验、检索、治理与 Memory Flush）

## 1. 元数据

| 字段 | 值 |
|---|---|
| Spec ID | `SPEC-005` |
| 状态 | `implemented` |
| 版本 | `1.0.0` |
| 创建日期 | 2026-08-19 |
| 最后更新 | 2026-08-19 |
| 实施阶段 | `06-implementation-plan.md` 阶段 5 |
| 前置依赖 | `SPEC-002`（认证隔离）、`SPEC-003`（上下文/compaction）、`SPEC-004`（工具运行时） |
| 后续依赖 | `SPEC-006`（待办提醒，记忆的 `task` 类型投影） |

来源：

- [产品需求](../../docs/01-product-requirements.md)：`FR-020~031`、`FR-040~045`、`FR-111/116`、`AC-020~025/063`、`PRD SEC-004~007/011~013`。
- [记忆、上下文与工具设计](../../docs/04-memory-context-tool-design.md)：第 2~6 节。
- [API、数据与安全设计](../../docs/05-api-data-security-design.md)：第 2.3、7、10 节。
- [参考源码分析](../../docs/02-reference-code-analysis.md)：`qmemory_runtime` 的候选→校验→apply→persist。
- [实施计划](../../docs/06-implementation-plan.md)：阶段 5。
- [测试计划](../../docs/07-test-plan.md)：`MEM-001~039`、`AG-010~019`、`SEC-030~035`、`E2E-020~029`。

## 2. 背景与问题

知伴的核心差异化是「可控记忆」：跨会话记住用户的偏好、习惯、目标和重要信息，并允许用户查看、编辑、删除。当前系统完全没有记忆能力：

1. 无记忆数据模型（`memories`、`memory_candidates` 表未建）。
2. 无候选提取：LLM 回复中「记住我喜欢简洁回答」不会被识别为记忆。
3. 无确定性校验：模型输出的候选无法通过服务端规则校验、去重、冲突检测。
4. 无检索：上下文组装时不会注入相关记忆。
5. 无治理：用户无法查看、编辑、删除记忆。
6. 无 Memory Flush：compaction 前不会把稳定历史写入记忆。

本 Spec 按文档第 2~6 节实现完整的记忆闭环，核心约束是：**LLM 只生成候选，确定性代码负责校验、权限、冲突、幂等和持久化**。

## 3. 目标

1. 建立记忆数据模型：`memories` + `memory_candidates` 表（含 pgvector embedding）。
2. 建立候选提取：显式记忆（用户明确要求）与隐式记忆（自动提取稳定信息）。
3. 建立确定性校验与决策：规范化、fingerprint、去重、冲突、reject_reason、add/update/delete/ignore。
4. 建立混合检索：user 硬过滤 + lexical(tsvector) + vector(pgvector) + 可解释评分。
5. 建立治理 API：记忆列表、查看、编辑、删除、撤销自动写入。
6. 建立上下文注入：检索相关记忆注入 Agent 上下文（受 Token 预算约束）。
7. 建立 Memory Flush：compaction 前抽取未处理的稳定历史写入记忆。
8. 建立 Embedding 适配器（text-embedding-3-small，1536 维），不可用时降级 lexical + recency。

## 4. 非目标

本步骤不实现：

- 记忆自动确认 UI（P1：记忆合并建议、冲突提示、类型筛选）。
- 重复提醒、提醒稍后处理（SPEC-006）。
- 记忆驱动 hint（P2：首页推荐池）。
- 数据导出（P1）。
- 真实 embedding 之外的模型切换（预留 adapter 接口，不做多模型管理）。

## 5. 已确认决策

| 决策 | 内容 |
|---|---|
| Embedding | `text-embedding-3-small`，通过 qproxy 网关，维度 1536 |
| 检索降级 | Embedding 不可用退化为 lexical + recency，写入先存正文后补 embedding |
| 范围 | 完整记忆闭环 P0（写入/检索/治理/Flush），记忆驱动 hint 等 P1/P2 延后 |

## 6. 目标目录契约

```text
apps/api/src/zhiban/
├── memory/
│   ├── types.py          # MemoryType 枚举、SourceKind、MemoryStatus
│   ├── schemas.py        # MemoryCandidatePayload、MemoryView 等 Pydantic
│   ├── ids.py            # fingerprint、conflict_key、candidate idempotency key
│   ├── normalize.py      # 文本规范化（NFKC、空白折叠）
│   ├── rejections.py     # RejectReason 枚举
│   ├── repository.py     # memories / memory_candidates 的 scope 访问
│   ├── validator.py      # 确定性校验规则
│   ├── service.py        # 候选→决策→持久化的领域逻辑
│   ├── extractor.py      # LLM 候选提取
│   ├── search.py         # 混合检索 + 评分
│   ├── flush.py          # Memory Flush
│   ├── router.py         # /memories REST API
│   └── tools.py          # memory.add/list/update/delete 工具
├── llm/
│   └── embedding.py      # EmbeddingAdapter（OpenAI 兼容）
└── db/
    └── models.py         # Memory、MemoryCandidate
```

## 7. 规范要求

### 7.1 记忆分类与字段

- **SPEC-MEM-001** 记忆类型 MUST 为 `identity/preference/habit/person/event/task/temporary/communication` 之一。
- **SPEC-MEM-002** 每条记忆 MUST 包含：`user_id`、`memory_type`、`subject`、`predicate`、`value`、`content`（渲染文本）、`source_kind`、`status`、`confidence`、`importance`、`fingerprint`、`conflict_key`、`embedding`、`source_message_ids`、`evidence_quote`、`expires_at`、`version`。
- **SPEC-MEM-003** `source_kind` MUST 为 `explicit/implicit/imported` 之一；显式记忆 `confidence=1.0`。
- **SPEC-MEM-004** `status` MUST 为 `active/superseded/deleted/expired` 之一；只有 `active` 进入检索。

### 7.2 候选提取

- **SPEC-MEM-010** 显式记忆请求（用户说「记住/以后按此偏好」等）MUST 被识别为 `explicit` 候选。
- **SPEC-MEM-011** 隐式记忆 MUST 只从 user 消息提取稳定信息，assistant 自述 MUST NOT 成为隐式记忆证据。
- **SPEC-MEM-012** 密码、令牌、验证码等敏感凭据 MUST NOT 自动保存为长期记忆。
- **SPEC-MEM-013** 隐式候选 `confidence < 0.65` MUST 忽略；`habit` 隐式候选要求 `>= 0.8` 或多次独立证据。
- **SPEC-MEM-014** 一次回复提取候选 MUST 有数量上限（默认 8）与频率限制。

### 7.3 校验、决策与幂等

- **SPEC-MEM-020** 候选 MUST 经 Pydantic Schema + 确定性规则双重校验。
- **SPEC-MEM-021** `source_message_ids` MUST 属于同一 user 且在本批次内；`evidence_quote` MUST 能在对应 user 消息中找到，否则拒绝。
- **SPEC-MEM-022** fingerprint = `SHA-256(user_id + type + subject + predicate + value)`；`UNIQUE(user_id, fingerprint) WHERE status='active'`。
- **SPEC-MEM-023** 候选幂等键 = `SHA-256(user_id + extractor_version + sorted(source_message_ids) + canonical_candidate)`。
- **SPEC-MEM-024** 决策顺序：精确重复→ignore（更新证据）；近重复→update；明确否定→delete；槽位冲突→supersede；无冲突→add。
- **SPEC-MEM-025** 冲突检测 MUST NOT 跨用户。
- **SPEC-MEM-026** 拒绝 MUST 记录 `reject_reason` 固定枚举（schema_invalid/unknown_type/empty_value/confidence_too_low/duplicate/等）。

### 7.4 检索

- **SPEC-MEM-030** 检索 MUST 先 SQL 层硬过滤 `user_id + status='active' + deleted_at IS NULL + (expires_at IS NULL OR expires_at > now())`，严禁先全库向量搜索再应用层过滤。
- **SPEC-MEM-031** 检索 MUST 混合召回：tsvector lexical Top 20 + pgvector cosine Top 20（相似度 >= 0.55），合并去重后最多 30。
- **SPEC-MEM-032** 评分 = `0.30*vector + 0.25*lexical + 0.15*recency + 0.12*importance + 0.10*confidence + 0.08*type_match`。
- **SPEC-MEM-033** 默认返回 6 条，硬上限 10；注入 token 预算默认 800。
- **SPEC-MEM-034** Embedding 不可用 MUST 退化为 lexical + recency，不返回未过滤的低相关记忆。

### 7.5 治理

- **SPEC-MEM-040** 用户 MUST 能列表、搜索、查看、编辑、删除自己的记忆。
- **SPEC-MEM-041** 删除 MUST 立即停止检索；缓存同步失效。
- **SPEC-MEM-042** 用户明确纠正已保存事实时，MUST 更新或删除相关记忆（不是临时忽略）。
- **SPEC-MEM-043** 编辑内容后 MUST 重算 fingerprint、清空旧 embedding、创建 embedding job。
- **SPEC-MEM-044** 撤销刚刚的自动记忆写入 MUST 可操作。

### 7.6 上下文注入

- **SPEC-MEM-050** 相关记忆 MUST 在上下文组装时注入，按 `system → summary → retrieved memories → recent → current user → tool results` 顺序。
- **SPEC-MEM-051** 注入 MUST 受 Token 预算（默认 800）约束，超限按分数截断，不截断单条中间。
- **SPEC-MEM-052** 注入门槛：`score >= 0.62` 且 `max(vector, lexical) >= 0.45`。
- **SPEC-MEM-053** 当前用户消息明确陈述与记忆冲突时，当前指令优先。

### 7.7 Memory Flush

- **SPEC-MEM-060** compaction 前 MUST 先执行 Memory Flush（抽取上次游标之后的稳定历史）。
- **SPEC-MEM-061** Flush 成功后推进 `memory_flushed_through_message_id` 游标；失败不推进，避免永久漏抽取。
- **SPEC-MEM-062** Flush 失败 MUST 记录 `memory_flush_failed`，不阻断聊天，也不把聊天改为失败。

### 7.8 Embedding 与安全

- **SPEC-MEM-070** Embedding MUST 通过 `EmbeddingAdapter` 隔离供应商，维度 1536。
- **SPEC-MEM-071** Embedding 不可用 MUST 降级：写入先存正文，Embedding 后补。
- **SPEC-MEM-072** 所有记忆查询 MUST 强制 user scope；向量、缓存键、后台任务均含 user 边界。

## 8. 行为与数据流

### 8.1 写入流水线

```text
对话完成
  -> Outbox 写 memory.extract job（同一事务）
  -> Worker 消费
  -> LLM 提取候选数组（严格 JSON Schema）
  -> Pydantic 校验 + 规则校验
  -> fingerprint + 去重 + 冲突检测
  -> 决策 add/update/delete/ignore
  -> 事务写候选 + 记忆
  -> 异步 embedding
```

### 8.2 检索流程

```text
用户消息
  -> 硬过滤 user_id/status/TTL（SQL 层）
  -> tsvector lexical Top 20 + pgvector cosine Top 20
  -> 合并去重（最多 30）
  -> 可解释评分
  -> 返回 Top 6（分数 >= 0.62）
  -> 注入上下文（Token 预算内）
```

## 9. 错误与降级语义

| 场景 | 行为 |
|---|---|
| Embedding 不可用 | 检索退化为 lexical + recency |
| LLM 提取失败 | 聊天正常完成，记录失败，后台补偿 |
| 候选校验失败 | 记录 reject_reason，不入库 |
| 重复候选 | decision=ignore，更新证据 |
| 记忆检索零结果 | 正常回答，不强制注入 |
| Flush 失败 | 不阻断聊天，不推进游标 |

## 10. 安全与隐私

- 记忆检索 SQL 在向量排序前包含 user_id 硬过滤。
- 敏感凭据不自动记忆。
- assistant-only 文本永不成为隐式记忆证据。
- 日志不记录记忆正文，只用 memory_id/长度/类型。
- 缓存键含 user 边界。

## 11. 验收标准

| 验收 ID | 必须结果 | 测试映射 |
|---|---|---|
| SPEC-MEM-AC-001 | 显式「记住」写入偏好记忆，带来源与时间 | `MEM-001`、`AC-020` |
| SPEC-MEM-AC-002 | 隐式候选提取 + 校验 + 去重 | `MEM-002~009`、`AC-025` |
| SPEC-MEM-AC-003 | 敏感凭据不自动记忆 | `MEM-012`、`AC-024`、`PRD SEC-012` |
| SPEC-MEM-AC-004 | 检索先 user 过滤，跨用户不串 | `MEM-025/035`、`AC-063`、`PRD SEC-005` |
| SPEC-MEM-AC-005 | 相关记忆影响回答，无关不注入 | `MEM-031/032`、`AC-021` |
| SPEC-MEM-AC-006 | 编辑后新值生效，删除后不再使用 | `MEM-017/019`、`AC-022/023` |
| SPEC-MEM-AC-007 | 遗忘后旧消息不静默恢复 | `MEM-021`、`AC-023` |
| SPEC-MEM-AC-008 | Embedding 降级 lexical 可用 | `MEM-028` |
| SPEC-MEM-AC-009 | 跨会话记忆召回端到端 | `E2E-020/021` |

## 12. 发布与回滚

- 新增 `memories`、`memory_candidates` 表（迁移 expand，单 head 可 downgrade）。
- Embedding 维度 1536 固定；切模型需新列/表，不混写。
- 回滚 = 回退迁移 + 停用记忆注入；不删除数据。

## 13. 偏差与决策

| 决策 | 说明 |
|---|---|
| Embedding 用 text-embedding-3-small | qproxy 网关可用，维度 1536，与文档 schema 一致 |
| 记忆自动确认 UI 延后 | P1：合并建议、冲突提示、类型筛选放后续 |
| 记忆驱动 hint 延后 | P2：首页推荐池不做 |
| 隐式提取走 Outbox | 异步抽取，失败不阻断聊天，可补偿 |
| 用户分类两层并存 | 保留技术型 memory_type（8 类）做后端逻辑（TTL/置信度/排序），新增 user-facing `category` 字段（基本信息/沟通禁忌/沟通偏好/其他）做展示 |
| 分类由提取时判断 | 模型在提取候选时直接输出 category，后端只做枚举校验 |
| 分层记忆注入 | 借鉴小 Q：explicit（主动记忆）每次全量注入（`[用户的核心信息与偏好]`），implicit（自动提取）按需召回（`[与当前问题相关的用户记忆]`） |
| Prompt 三层结构 | 借鉴小 Q：base（身份+行为铁律）+ tool_use（工具路由）+ memory_rules（记忆行为规则），每次 query 组装 |

## 14. 开放问题

- 隐式提取的触发时机：每条消息后立即，还是定时批量？
- 显式记忆的确认流程：立即保存还是需用户确认？
- `task` 类型记忆与 SPEC-006 待办的投影关系。
