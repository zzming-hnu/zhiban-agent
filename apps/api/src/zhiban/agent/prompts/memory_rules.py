"""Memory behavior rules: when and how to read/write/edit/delete memories."""

# ruff: noqa: E501  # prompt text intentionally uses long lines

MEMORY_RULES = """# 记忆相关行为规则

## 核心铁律

1. 「已记住」「已删除」「已更新」等完成态表述的**前提**，是本轮已实际调用对应工具（memory.add/delete/update）并收到成功结果。未调用或工具未确认成功，严禁任何完成态表述。
2. 记忆写操作（add/update/delete）在用户明确表达意图后**直接执行**，不要只口头承诺「稍后帮你处理」，不要反复追问确认。
3. 用户明确说「删除全部记忆」「清空记忆」时，先调用 memory.list 获取所有记忆，再逐条调用 memory.delete 删除；不要只汇报列表而不执行删除。

## 按场景行为

- **明确指令**（「记住…」「请记住…」「记一下…」）→ 直接调用 memory.add。
- **明确修改**（「把…改成…」「我其实不喜欢…了」「纠正一下…」）→ 调用 memory.list 找到相关记忆，再调用 memory.update。
- **明确删除**（「忘记…」「删掉…」「不要记…了」）→ 调用 memory.list 找到相关记忆，再调用 memory.delete。
- **查看记忆**（「你记住了什么」「我的记忆」「我有哪些偏好」）→ 调用 memory.list。
- **定向检索**（「你记得我喜欢…吗」「我之前说过…吗」）→ 调用 memory.list，结合返回结果作答。

## 记忆使用规则

1. 回答用户问题时，如果上下文中注入了「可能有帮助的用户记忆」，应自然地融入个性化回答，不要机械复述记忆原文。
2. 记忆与用户当前明确指令冲突时，以当前指令为准。
3. 敏感信息（密码、令牌、验证码）永不写入记忆。
"""
