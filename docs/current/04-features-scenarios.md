# 知伴 · 功能场景

> 反映当前真实实现（2026-08-20）。每个场景描述用户意图、系统行为、最终结果。

## 1. 连续对话

| 场景 | 用户输入示例 | 系统行为 |
|---|---|---|
| 闲聊 | 「你好」 | 主 Agent 直接回答（不路由 subagent） |
| 多轮追问 | 「帮我写个周报开头」「再精简一点」 | 保留上下文，基于历史回答 |
| 长对话压缩 | 连续 20+ 轮 | 超 Token 阈值自动滚动摘要，旧消息折叠 |
| 断线恢复 | 刷新页面 | 从 run 快照恢复，不重复生成 |

## 2. 可控记忆

### 2.1 主动记忆（用户明确要求）

| 场景 | 输入 | 行为 |
|---|---|---|
| 记住事实 | 「记住我喜欢喝少糖咖啡」 | 路由 MemoryAgent → `memory.add` → 存 preference |
| 记住身份 | 「我叫张振明」 | 提取 identity → 分类强制 basic_info |
| 查看记忆 | 「你记得我什么」 | `memory.list` → 展示所有记忆 |
| 修改记忆 | 「我其实不喜欢咖啡了」 | `memory.list` + `memory.update` |
| 删除记忆 | 「忘掉我的咖啡偏好」 | `memory.list` + `memory.delete` |

### 2.2 自动记忆（对话中隐式提取）

对话结束后，Worker 异步抽取值得长期保存的信息（如用户提到的职业、偏好、习惯），走「候选提取 → 校验 → 决策」链路。

### 2.3 记忆分类展示

记忆页按四个用户类别 Tab 展示：
- **基本信息**：身份、职业、相关人物（identity/person/event 强制归此）
- **沟通禁忌**：用户不希望的方式（如「别用 emoji」）
- **沟通偏好**：用户喜欢的方式（如「回答简洁」）
- **其他**：不属于以上三类的

### 2.4 记忆注入个性化

下次对话时，explicit 记忆全量注入、implicit 按需召回，实现「记得你之前说过什么」。

## 3. 待办与提醒

### 3.1 待办

| 场景 | 输入 | 行为 |
|---|---|---|
| 创建待办 | 「帮我记个待办：明天交周报」 | 路由 TaskAgent → `todo.create` |
| 带截止时间 | 「明天下午3点交周报」 | `todo.create` + due_at |
| 完成待办 | 待办页勾选 | `todo.complete` |
| 取消待办 | 待办页删除 | `todo.cancel` |

### 3.2 单次提醒

| 场景 | 输入 | 行为 |
|---|---|---|
| 单次提醒 | 「明天9点提醒我开会」 | `reminder.create`（recurrence=none） |
| 相对时间 | 「下午3点提醒我」 | 推断为今天/明天具体时间 |

### 3.3 周期提醒

| 场景 | 输入 | 行为 |
|---|---|---|
| 每天 | 「每天早上7点提醒我喝水」 | `reminder.create`（recurrence=daily） |
| 每周 | 「每周一上午提醒我交周报」 | `reminder.create`（recurrence=weekly） |
| 带结束时间 | 「每天提醒我，持续一周」 | recurrence + recurrence_end_at |

### 3.4 三路触达

提醒到点时：
1. 站内 toast（前端轮询 `pending-notifications`）
2. 浏览器通知（Notification API）
3. 邮件（SMTP，需配置）

## 4. 联网搜索

| 场景 | 输入 | 行为 |
|---|---|---|
| 实时信息 | 「搜索今天有什么科技新闻」 | 路由 SearchAgent → `web_search` |
| 事实查证 | 「查一下 DeepSeek 最新模型」 | SearXNG 搜索 + 引用 |
| 无网络 | 搜索请求 | 降级说明「无法获取实时信息」 |

## 5. 工具调用链路（Function Calling 完整展示）

以「帮我记个待办：明天交周报」为例：

```
用户输入
  → 主 Agent 路由决策（LLM）：target=task
  → 委派 TaskAgent
       TaskAgent 内部 mini-ReAct：
         round 1: LLM 决定调 todo.create(due_at=明天)
                  → 工具执行成功 → "已创建待办：交周报"
       返回结构化摘要
  → 主 Agent 基于摘要流式生成最终回复：
     "好的，已帮你创建待办「交周报」，截止明天。"
```

前端看到的完整链路（SSE 事件）：`run.started(delegated=true) → message.delta... → message.completed → run.completed`

## 6. 数据隐私

| 场景 | 行为 |
|---|---|
| 用户隔离 | 每个用户只能访问自己的数据（跨用户返回 404） |
| 密码安全 | Argon2id 哈希，永不明文存储 |
| 会话安全 | HttpOnly Cookie，前端 JS 无法读取 |
| 日志脱敏 | 正文/密码/Token 不落日志 |
| Prompt 注入防护 | role=user 内容不当指令执行 |
