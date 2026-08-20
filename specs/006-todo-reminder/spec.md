# SPEC-006：待办、单次应用内提醒与任务跟踪

## 1. 元数据

| 字段 | 值 |
|---|---|
| Spec ID | `SPEC-006` |
| 状态 | `implemented` |
| 版本 | `1.0.0` |
| 创建日期 | 2026-08-19 |
| 最后更新 | 2026-08-19 |
| 实施阶段 | `06-implementation-plan.md` 阶段 6 |
| 前置依赖 | `SPEC-002`（认证隔离）、`SPEC-004`（工具运行时）、`SPEC-005`（Worker/jobs 基础设施） |
| 后续依赖 | `SPEC-007`（hardening/release） |

来源：

- [产品需求](../../docs/01-product-requirements.md)：`FR-050~061`、`FR-090~096`、`AC-030~035`、`PRD SEC-004/006/009/010`。
- [API、数据与安全设计](../../docs/05-api-data-security-design.md)：第 2.4、7（todos/reminders 表）、9（后台任务/Outbox）。
- [参考源码分析](../../docs/02-reference-code-analysis.md)：`qq_agents_common` 的 Todo/Schedule/Outbox。
- [实施计划](../../docs/06-implementation-plan.md)：阶段 6。
- [测试计划](../../docs/07-test-plan.md)：`TOOL-030~039`、`IT-030~039`、`E2E-030~039`、`DR-010~014`。

## 2. 背景与问题

当前知伴能聊天、能记住偏好，但用户说的「待办」「提醒」只是模型口头回应，没有真实状态：

1. 无 `todos`/`reminders` 表，行动项不持久化。
2. 无待办/提醒工具，Agent 无法通过工具创建真实实体。
3. 无 Worker 调度，到点提醒无法触发。
4. 无时区处理，「明天9点」无法按用户时区正确解释。
5. 无幂等投递，重复触发可能产生重复提醒。
6. 任务跟踪靠模型瞎猜，不基于真实待办状态。

本 Spec 让「对话里的行动项」变成真实、可到点提醒、可追踪状态的任务。

## 3. 目标

1. 建立 `todos`、`reminders` 表（含用户作用域、状态、版本、幂等键）。
2. 建立待办/提醒工具（Agent 可调用）：创建、列表、完成、编辑、取消。
3. 建立提醒调度：Worker 扫描到期提醒，幂等投递到应用内提醒中心。
4. 建立时区处理：存储 UTC + 用户 IANA 时区，含糊时间澄清，DST 处理。
5. 建立任务跟踪：基于已保存待办状态回答进度。
6. 建立 Mock clock（演示用，推进时间触发提醒，不依赖真实等待）。
7. 建立前端待办/提醒页面。

## 4. 非目标

本步骤不实现：

- 重复提醒（每日/每周 cron）、提醒稍后处理（P1）。
- 真实短信/邮件/系统推送；只做应用内提醒。
- 任务拆解、进度备注、按目标聚合（P1）。
- 日历/邮件第三方集成。

## 5. 已确认决策

| 决策 | 内容 |
|---|---|
| 提醒投递 | 应用内提醒中心（不接真实推送） |
| 时区 | 存储 UTC + 用户 IANA 时区，含糊时间请求澄清 |
| 演示 | Mock clock 推进时间触发提醒 |
| 幂等 | at-least-once 消费 + 幂等投递（不声称 exactly-once） |

## 6. 目标目录契约

```text
apps/api/src/zhiban/
├── todos/
│   ├── models.py       # Todo、Reminder（或并入 db/models.py）
│   ├── schemas.py      # 请求/响应
│   ├── service.py      # 待办/提醒领域逻辑
│   ├── repository.py   # scope 访问
│   ├── router.py       # /todos /reminders REST
│   └── tools.py        # todo.* / reminder.* 工具
├── workers/
│   └── reminder_jobs.py  # 提醒调度 + 投递 handler
└── db/
    └── models.py       # Todo、Reminder 表
```

## 7. 规范要求

### 7.1 待办

- **SPEC-TODO-001** 用户 MUST 能通过自然语言创建待办，提取标题与可选截止时间。
- **SPEC-TODO-002** 待办状态 MUST 为 `pending/done/cancelled` 之一；可标记逾期。
- **SPEC-TODO-003** 关键信息缺失/歧义时 MUST 请求补充或展示确认，不静默创建错误待办。
- **SPEC-TODO-004** 待办 MUST 有 `user_id` 强制作用域，跨用户访问 404。
- **SPEC-TODO-005** 完成/取消待办 MUST 幂等。

### 7.2 提醒

- **SPEC-REM-001** 用户 MUST 能创建带明确日期时间的单次提醒。
- **SPEC-REM-002** 提醒时间 MUST 按用户 IANA 时区解释，存储 UTC，确认时回显完整时间。
- **SPEC-REM-003** 过去时间、无效日期、含糊时间 MUST 提示修正，不静默创建。
- **SPEC-REM-004** 提醒状态 MUST 为 `scheduled/delivering/delivered/cancelled`。
- **SPEC-REM-005** 到点后 MUST 投递到应用内提醒中心；用户离线时下次进入可见未读/逾期。
- **SPEC-REM-006** 修改提醒后旧调度 MUST 失效，使用最新时间。
- **SPEC-REM-007** 取消提醒与 Worker 抢占并发时，不产生取消后的投递。

### 7.3 调度与幂等投递

- **SPEC-REM-010** Worker MUST 扫描 `status=scheduled AND remind_at <= now()` 的提醒。
- **SPEC-REM-011** 投递 MUST 使用 `event_key` 幂等，重复消费只产生一次可见提醒。
- **SPEC-REM-012** 投递 MUST 采用 at-least-once + 幂等，不声称 exactly-once。
- **SPEC-REM-013** 投递失败 MUST 重试（退避），超限进 dead 并保留原因。
- **SPEC-REM-014** Worker 重启/重复消费 MUST 不产生重复投递。

### 7.4 时区

- **SPEC-TZ-001** 时间统一存 UTC，用户时区存 IANA 名称。
- **SPEC-TZ-002** DST 缺失/重复时刻 MUST 澄清或按文档化规则处理。
- **SPEC-TZ-003** Agent 回显提醒时必须带绝对时间 + 时区。

### 7.5 任务跟踪

- **SPEC-TRK-001** 用户问进度时，MUST 基于已保存待办状态回答（完成/逾期/临近数），不凭聊天猜。
- **SPEC-TRK-002** 任务页 MUST 按状态展示待办与提醒。

### 7.6 工具

- **SPEC-TOOL-001** 提供 `todo.create/list/complete/cancel` 工具。
- **SPEC-TOOL-002** 提供 `reminder.create/list/cancel` 工具。
- **SPEC-TOOL-003** 写工具 MUST 幂等（operation_key）。
- **SPEC-TOOL-004** 工具参数（时间）服务端 MUST 校验，不信任模型自由文本。

### 7.7 Mock clock（演示）

- **SPEC-CLOCK-001** MUST 提供 Mock clock 能力，推进时间触发到期提醒，不依赖真实等待。
- **SPEC-CLOCK-002** Mock clock MUST 明确标识，不与真实时间混淆。

## 8. 行为与数据流

### 8.1 创建提醒

```text
用户："明天上午9点提醒我交报告"
  -> Agent 识别 reminder.create 意图
  -> 工具提取时间，按用户时区转 UTC
  -> 含糊时间 -> 请求澄清
  -> 写入 reminders 表（status=scheduled）
  -> 回显绝对时间 + 时区
```

### 8.2 调度投递

```text
Worker 扫描 reminders（scheduled + remind_at <= now）
  -> 状态置 delivering + 写 outbox（event_key）
  -> Dispatcher 投递到提醒中心
  -> 成功 -> delivered；失败 -> 重试/dead
```

## 9. 错误与降级语义

| 场景 | 行为 |
|---|---|
| 含糊时间 | 请求澄清，不创建 |
| 过去时间 | 提示修正 |
| 时区无效 | 回退用户默认时区或请求澄清 |
| 投递失败 | 重试，超限 dead，保留原因 |
| 重复投递 | 幂等去重，只投一次 |
| Worker 不可用 | 提醒保留，恢复后补偿扫描 |

## 10. 安全与隐私

- 待办/提醒查询强制 user scope。
- 时间/参数服务端校验，不信任模型自由文本。
- 日志不记录提醒全文。
- 幂等键含 user 边界。

## 11. 验收标准

| 验收 ID | 必须结果 | 测试映射 |
|---|---|---|
| SPEC-TODO-AC-001 | 对话创建待办，任务页可见 | `FR-050`、`AC-030`、`E2E-030` |
| SPEC-TODO-AC-002 | 完成/取消待办状态一致 | `FR-056`、`AC-033` |
| SPEC-REM-AC-001 | 创建提醒，回显绝对时间+时区 | `FR-052/053`、`AC-030` |
| SPEC-REM-AC-002 | 到点投递一次（Mock clock） | `FR-057`、`AC-032`、`E2E-032` |
| SPEC-REM-AC-003 | 重复消费不重复投递 | `FR-059`、`AC-034`、`IT-031` |
| SPEC-REM-AC-004 | 修改提醒用最新时间 | `FR-060`、`IT-035` |
| SPEC-TZ-AC-001 | 时区/DST 正确 | `UT-009`、`TOOL-033` |
| SPEC-TRK-AC-001 | 进度基于真实待办状态 | `FR-091`、`AC-035` |
| SPEC-CLOCK-AC-001 | Mock clock 推进触发提醒 | `FR-057`、`E2E-039` |

## 12. 发布与回滚

- 新增 `todos`、`reminders` 表（迁移 expand，单 head 可 downgrade）。
- 回滚 = 回退迁移 + 停用提醒工具；不删除数据。

## 13. 偏差与决策

| 决策 | 说明 |
|---|---|
| 应用内提醒 | P0 不做真实推送，符合文档 AC-032「应用内提醒中心」 |
| Mock clock | 演示用，不依赖真实时间等待 |
| 提醒不做重复规则 | P1 的每日/每周 cron 延后，本 Spec 只做单次提醒 |

## 14. 开放问题

- 提醒中心的 UI 形态（独立页面 vs 侧边栏弹窗）。
- Mock clock 的实现（配置开关 vs 独立 API）。
