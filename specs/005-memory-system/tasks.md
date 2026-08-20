# SPEC-005 任务清单

状态：`implemented`

本清单只在完成真实变更和验证后勾选。任务按依赖顺序排列；同一组中标注「可并行」的项目可以并行。

## T0：规格准备

- [x] `MEM-T000` 编写 `SPEC-005` 的目标、边界、要求和验收映射。
- [x] `MEM-T001` 确认决策：隐式异步提取、显式立即保存、引入 Worker。
- [x] `MEM-T002` 实现开始时将 `spec.md` 状态改为 `in_progress`。

## T1：数据模型与迁移

- [x] `MEM-T010` 新增 `jobs`、`outbox_events` 表。
- [x] `MEM-T011` 新增 `memories` 表（含 fingerprint、conflict_key、embedding vector(1536)、TTL、version）。
- [x] `MEM-T012` 新增 `memory_candidates` 表。
- [x] `MEM-T013` 唯一索引：fingerprint、idempotency_key。
- [x] `MEM-T014` HNSW embedding 索引。
- [x] `MEM-T015` Alembic 迁移（单 head），upgrade/downgrade 验证通过。

## T2：Worker 基础设施

- [x] `MEM-T020` jobs claim/lease/retry（FOR UPDATE SKIP LOCKED）。
- [x] `MEM-T021` Worker 消费循环。
- [x] `MEM-T022` Outbox/job 事务写。
- [x] `MEM-T023` job 类型注册与分发（memory.extract）。

## T3：记忆领域基础

- [x] `MEM-T030` 枚举（MemoryType/SourceKind/MemoryStatus/RejectReason/MemoryCategory）。
- [x] `MEM-T031` 文本规范化（NFKC、空白折叠）。
- [x] `MEM-T032` fingerprint/conflict_key/candidate idempotency key。
- [x] `MEM-T033` MemoryCandidatePayload/MemoryView schema。
- [x] `MEM-T034` MemoryRepository（user scope + SQL TTL 过滤）。

## T4：候选提取

- [x] `MEM-T040` 显式记忆识别。
- [x] `MEM-T041` LLM 候选提取（严格 JSON，含 category）。
- [x] `MEM-T042` 隐式规则（敏感排除、置信度阈值）。
- [x] `MEM-T043` 提取数量/频率限制。

## T5：校验与决策

- [x] `MEM-T050` 确定性校验。
- [x] `MEM-T051` 决策（ignore/update/delete/supersede/add）。
- [x] `MEM-T052` reject_reason 记录。
- [x] `MEM-T053` 候选幂等。

## T6：检索与注入

- [x] `MEM-T060` EmbeddingAdapter（text-embedding-3-small）。
- [x] `MEM-T061` 混合检索（tsvector ILIKE + pgvector + 评分）。
- [x] `MEM-T062` 评分公式与注入门槛。
- [x] `MEM-T063` Embedding 降级（lexical + recency）。
- [x] `MEM-T064` 上下文注入记忆。

## T7：治理 API 与工具

- [x] `MEM-T070` /memories REST API。
- [x] `MEM-T071` memory.add/list/update/delete 工具。
- [x] `MEM-T072` 撤销自动写入（软删除）。
- [x] `MEM-T073` 编辑后重算 fingerprint、清空 embedding。

## T8：Memory Flush

- [x] `MEM-T080` Flush 游标。
- [x] `MEM-T081` compaction 前调用（通过 run 后异步 job）。
- [x] `MEM-T082` Flush 失败不阻断聊天。

## T9：前端对齐

- [x] `MEM-T090` 记忆管理页（/memories，按 category 分组、编辑、删除）。
- [x] `MEM-T091` 对话中记忆使用（注入记忆到上下文）。
- [x] `MEM-T092` 记忆写入（memory.add 工具）。

## T10：测试

- [x] `MEM-T100` 数据模型/迁移测试。
- [x] `MEM-T101` Worker claim/lease/retry 测试。
- [x] `MEM-T102` 候选提取/校验/决策测试。
- [x] `MEM-T103` 检索排序/降级/跨用户隔离测试。
- [x] `MEM-T104` 治理 API + 工具测试。
- [x] `MEM-T105` category 分类测试。

## T11：文档与验证

- [x] `MEM-T110` 完成 `verification.md`。
- [x] `MEM-T111` 更新 `docs/progress/005-memory-system.md`。
- [x] `MEM-T112` 更新 README 与 Spec 状态。

## 完成规则

- `SPEC-MEM-AC-001~009` 均有真实结果。
- 记忆写入（显式+隐式）、检索、治理、Flush 均有自动化测试证据。
- 跨用户隔离、敏感凭据排除、Embedding 降级有专项测试。
- Worker 链路可用。
- mypy strict 全绿，无 override。
- 用户分类（基本信息/沟通禁忌/沟通偏好/其他）可视化。
