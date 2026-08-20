# 知伴 Spec 规范

本目录是“知伴”项目实现规格的唯一入口。所有业务代码、数据库迁移、接口和基础设施变更，必须先有可验收的 Spec，再进入实现。

## 1. 规范目标

Spec 用于回答五个问题：

1. 为什么要做，解决什么问题。
2. 本次做什么、不做什么。
3. 对外行为、状态和失败语义是什么。
4. 如何验证完成，而不是仅验证“代码已写”。
5. 实现结果与原规格有哪些差异。

Spec 不替代产品需求和总体架构：

- 产品范围和验收来源：[产品需求](../docs/01-product-requirements.md)。
- 总体技术边界：[技术架构](../docs/03-technical-architecture.md)。
- 记忆、上下文和工具规则：[记忆、上下文与工具设计](../docs/04-memory-context-tool-design.md)。
- API、数据和安全边界：[API、数据与安全设计](../docs/05-api-data-security-design.md)。
- 实施顺序：[实施计划](../docs/06-implementation-plan.md)。
- 测试编号：[测试计划](../docs/07-test-plan.md)。

当专题 Spec 与总体方案冲突时，不得静默选择其一：必须在 Spec 的“偏差与决策”中记录原因，并同步修改受影响的总体文档。

## 2. 目录与命名

每个实现步骤使用独立目录：

```text
specs/
├── README.md
└── NNN-short-name/
    ├── spec.md
    ├── tasks.md
    └── verification.md
```

- `NNN`：三位递增编号，如 `001`、`002`。
- `short-name`：小写 kebab-case，表达交付物而非团队名称。
- `spec.md`：实现前规范。
- `tasks.md`：可执行任务清单和依赖关系。
- `verification.md`：实现后填写的真实验证记录；不得预填“通过”。

每个步骤还应在 `docs/progress/NNN-short-name.md` 维护面向项目过程的摘要，记录范围、关键决策、变更文件、验证结果、已知问题和下一步。

## 3. 状态模型

Spec 状态只允许：

```text
draft -> ready -> in_progress -> implemented -> verified
                  |              |
                  +-> blocked    +-> partial
```

- `draft`：仍有影响实现的开放问题。
- `ready`：目标、边界、验收和依赖已明确，可以开始编码。
- `in_progress`：正在实现。
- `implemented`：代码完成，但验证尚未全部结束。
- `verified`：所有必须验收项有真实证据。
- `partial`：已交付部分范围，未完成项明确记录。
- `blocked`：存在外部或用户决策阻塞。

状态变化必须同步更新 `spec.md` 元数据和过程文档。不能因为代码合并就直接标记 `verified`。

## 4. 规范用语

- **MUST / 必须**：不满足即不能验收。
- **MUST NOT / 禁止**：不可出现的行为。
- **SHOULD / 应当**：默认需要满足；偏离必须说明理由。
- **MAY / 可以**：可选能力，不影响本步骤验收。

需求使用稳定编号：

- Spec 内部要求：`SPEC-<域>-NNN`，例如 `SPEC-FND-001`。
- 产品需求：沿用 `FR/NFR/PRD SEC/AC-xxx`。
- 测试：沿用 `UT/IT/API/AG/MEM/TOOL/SEC/E2E/PERF/DR-xxx`。
- 架构决策：`ADR-NNNN`。

禁止使用没有定义的临时编号，如 `FR-AUTH`、`NFR-TOOL`。

## 5. `spec.md` 必备结构

每份 Spec 必须包含：

1. 元数据：ID、状态、版本、创建/更新时间、依赖、来源文档。
2. 背景与问题。
3. 目标。
4. 非目标。
5. 用户或系统场景。
6. 规范要求：每项带稳定编号。
7. 行为、状态与数据流。
8. 接口、数据或目录契约。
9. 错误与降级语义。
10. 安全与隐私。
11. 可观测性。
12. 验收标准及测试映射。
13. 发布、回滚或迁移策略。
14. 偏差与决策。
15. 开放问题。

只有纯文档或极小机械修改，才可在说明理由后精简章节。

## 6. Definition of Ready

进入 `ready` 前必须满足：

- 目标和非目标明确。
- 所有 MUST 要求有编号。
- 产品需求和测试计划能追踪到本 Spec。
- API、状态、数据结构或目录边界已明确到可实现。
- 安全、隔离、幂等、失败语义已考虑。
- 外部依赖及 Mock/Fake 方案明确。
- 没有会显著改变实现方向的开放问题。

## 7. Definition of Done

进入 `verified` 前必须满足：

- `tasks.md` 的必须任务完成。
- 实现与 Spec 一致；偏差已记录并同步相关文档。
- 对应自动化测试、静态检查和必要手工验证已实际执行。
- `verification.md` 记录命令、环境、结果和失败项，不只写结论。
- 过程文档列出变更文件、关键决策、遗留风险和下一步。
- 不包含密钥、个人数据或伪造的测试结果。

## 8. 变更控制

实现过程中若需要改变范围：

1. 先更新当前 Spec 的“偏差与决策”。
2. 判断是否影响产品需求、总体架构、API、安全或测试文档。
3. 影响外部契约时增加 Spec 版本，并记录兼容或迁移策略。
4. 破坏性或不可逆变更必须先停下并获得用户确认。

小型实现细节可以在不改变验收和外部行为时直接调整，但仍应写入过程文档。

## 9. 验证记录规则

`verification.md` 只记录实际发生的事实：

```text
执行时间：
环境：
命令：
退出码：
通过项：
失败项：
未执行项及原因：
```

- “计划运行”“应该通过”不能写成“已通过”。
- 外部服务使用 Fake/Mock 时必须明确标注。
- 性能数字必须记录数据规模、并发、硬件和采样方式。
- 手工检查必须写明步骤和观察结果。

## 10. 首批 Spec 顺序

1. `001-project-foundation`：工程结构、工具链、配置、健康检查和质量门禁。
2. `002-auth-conversation`：认证、用户隔离、会话和消息。
3. `003-streaming-agent`：SSE、LLM Adapter、上下文与有界 Agent。
4. `004-tool-runtime`：Registry、Executor、Mock Search 与 Summary。
5. `005-memory-system`：候选、校验、检索、治理与 Memory Flush。
6. `006-todo-reminder`：待办、提醒、Jobs/Outbox 和 Worker。
7. `007-hardening-release`：安全、观测、E2E、部署与答辩固化。

后续编号可以拆分，但不得绕过 Spec 直接实现。
