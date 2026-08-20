# 知伴：已知限制

本文如实记录当前实现（SPEC-001~007）的已知限制，供答辩说明，避免把「目标」说成「已完成」。

## 1. 功能限制

| 限制 | 说明 | 计划 |
|---|---|---|
| 真实搜索依赖自建 SearXNG | 需本地 Docker 跑 SearXNG 容器；无网时切换 `SEARCH_PROVIDER=mock` | P1 接付费搜索 API |
| 提醒不做重复规则 | 只支持单次提醒，无每日/每周 cron | P1 |
| 提醒「稍后处理」（snooze） | 未实现 | P1 |
| 记忆自动确认 UI | 记忆合并建议、冲突提示、类型筛选未做 | P1 |
| 记忆驱动 hint | 首页推荐池未做 | P2 |
| 社交草稿自动发送 | 只生成草稿，不自动发送（符合 P0 边界） | 非目标 |
| 数据导出 | 未实现 | P1 |

## 2. 工程限制

| 限制 | 说明 |
|---|---|
| 单机部署 | 单实例 API + Worker，无多副本 run 锁（跨实例放后续） |
| 无完整熔断器 | 只做超时 + 重试，无滑动窗口熔断矩阵 |
| 无完整监控平台 | 结构化日志 + request_id 关联，无 Prometheus/Grafana |
| Token 估算为近似 | 中文按字符、英文按词估算，未接 tiktoken |
| Embedding 检索依赖网关 | text-embedding-3-small 通过 qproxy 网关，无独立 embedding 服务 |

## 3. 未实测项

| 项 | 状态 |
|---|---|
| GitHub 远程 CI | 目录未初始化 Git，workflow 未远程执行 |
| 性能压测 | 只做 smoke 基线，未做文档中的完整 PERF 压测 |
| 跨进程取消广播 | 只做进程内协程取消 |
| 断线重连浏览器级验证 | 代码已实现，未做浏览器断线 E2E |

## 4. 演示依赖

| 依赖 | 说明 |
|---|---|
| LLM | Kimi K2.5（qproxy 网关），需网络 |
| 搜索 | SearXNG（本地容器），需网络；无网切 Mock |
| Embedding | text-embedding-3-small（qproxy 网关） |
| 基础设施 | PostgreSQL + pgvector、Redis、Docker/Colima |
