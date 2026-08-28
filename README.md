# 知伴（ZhiBan）

> 一个具备「可控记忆 + 可靠工具调用 + 多轮对话」能力的个人 AI 助理，从 0 到 1 全栈实现。

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2Bpgvector-336791.svg)](https://www.postgresql.org/)

知伴是一个可本地运行、可体验、可测试的 AI Agent 应用。它记住你的偏好和重要信息，帮你在多轮对话中完成任务，并支持待办提醒、联网搜索等常用能力。

## ✨ 核心能力

- 🧠 **可控记忆** — 主动/自动提取记忆，按类别展示（基本信息/沟通禁忌/沟通偏好/其他），用户可编辑；记忆会随用户变化而演化、随积累而自我去重
- 🔍 **可解释的语义检索** — 混合检索（向量 + 中文分词词法）+ 六因子可解释打分，换个问法也能召回，并能说明"为什么想起这条"
- 🔧 **可靠工具调用** — Function Calling 完整链路：注册、路由、执行、幂等、审计
- 📋 **待办与提醒** — 单次 + 周期提醒（每天/每周），站内 toast + 浏览器通知 + 邮件三路触达
- 🌐 **联网搜索** — 真实联网搜索，结果去重 + 来源可信度分级，优先权威信息
- 💬 **多轮对话** — 流式输出、Markdown 渲染、上下文滚动摘要压缩
- 🤖 **主 Agent - Subagent 架构** — 主 Agent 路由 + 管理 ReAct，Memory/Task/Search 三个专业 subagent

## 🎯 深度优化亮点

### 记忆的自我整合与演化（核心差异化）

记忆不是静态快照，而是**会随用户变化而演化、随积累而自我去重**：

- **自然语言 fact 范式**：记忆以一句自然语句存储（如「用户不喜欢吃辣」），而非易出错的结构化三元组，根治"用户 喜欢吃 用户 不喜欢吃辣"这类抽取畸形
- **语义去重**：主动/自动两条提取路径之间做词法相似度去重（含否定极性判断），已记过的信息不会重复记
- **主动记忆调和（reconcile）**：用户明确说"记住 X"时，模型判断是新增/更新/取代/重复，实现正反偏好的演化（"喜欢辣"→"不喜欢辣"自动取代旧值，而非并存两条）
- **演化链**：记忆变化时保留历史（`superseded_by` 串联），支持"你之前……现在……"的时间追问
- **核心原则**：LLM 只提议、确定性代码裁决，杜绝幻觉误删

### 可解释的混合检索（记忆）

记忆检索不是简单的关键词匹配，而是**可评估、可调优、可解释**的检索系统：

- **混合召回**：向量（bge-m3 + pgvector）+ 词法（jieba 分词 + BM25），解决中文语义匹配
- **六因子打分**：向量相似度 + 词法相关 + 时效衰减（遗忘曲线）+ 重要度 + 置信度 + 类型
- **数据驱动调优**：建立评测集（recall@k / nDCG / MRR），网格搜索自动调参，`recall@3` 从 **0.400 → 0.900**（+125%），词法降级从 0 → 0.700
- **可解释性**：每次召回输出各因子得分，前端展示"召回了哪些记忆 + 相关度"
- 详见 [`docs/current/07-memory-retrieval-optimization.md`](docs/current/07-memory-retrieval-optimization.md)

### 搜索质量工程

- **结果去重**：URL 归一化（去 tracking 参数）+ 标题相似度判重
- **来源可信度分级**：权威媒体（gov/edu/百科/凤凰/网易/CSDN/知乎/GitHub 等）> 社区 > 个人博客，优先采用权威信息

## 🏗️ 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui |
| 后端 | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 |
| LLM | DeepSeek（`deepseek-v4-flash` / `deepseek-v4-pro`） |
| Embedding | BAAI/bge-m3（1024 维，国内直连） |
| 存储 | PostgreSQL + pgvector |
| 缓存/队列 | Redis |
| 后台任务 | 独立 Worker（jobs/outbox 模式） |
| 联网搜索 | Bocha Search API（可降级 SearXNG / Mock） |
| 测试 | pytest（150）· vitest · Playwright |

## 🚀 快速开始

### 前置要求

- Node.js >= 22
- Python 3.12
- [uv](https://github.com/astral-sh/uv)
- Docker（或 macOS 上的 Colima）

### 一键部署（Docker Compose）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填入 LLM_API_KEY（DeepSeek 密钥）

# 2. 构建并启动
make stack-build
make stack-up

# 3. 验证
make smoke
```

### 本地开发

```bash
# 启动基础设施
colima start
make infra-up

# 安装依赖
make setup

# 启动开发进程
make dev
```

访问：
- Web 首页：http://localhost:3000
- API 文档：http://localhost:8000/api/docs
- 健康检查：http://localhost:8000/api/v1/health/live

## 🧪 体验指南

### 演示账号

| 账号 | 密码 | 用途 |
|---|---|---|
| `demo-a@example.com` | `demo12345` | 主演示账号（含一条偏好记忆 + 一个待办） |
| `demo-b@example.com` | `demo12345` | 隔离验证账号（验证跨用户数据不串） |

> 演示账号仅用于体验，`make reset-demo && make seed-demo` 可重置为初始状态。

### 推荐体验路径（按顺序）

**① 记忆演化（核心亮点）**

```
1. 对 AI 说「记住我不吃辣」
2. 再说「其实我现在能吃辣了」
3. 问「我之前关于吃辣是怎么说的？」
```

预期：AI 能回答出「你之前不吃辣，现在能吃辣了」——记忆会随用户变化而演化，而不是记两条或丢历史。可在「记忆」页看到演化结果。

**② 主动/自动去重**

```
1. 说「记住我喜欢喝咖啡」
2. 打开「记忆」页，观察咖啡相关记忆只有一条
```

预期：主动记忆和后台自动提取不会重复记同一条信息。

**③ 待办与提醒**

```
1. 说「明天上午 9 点提醒我提交材料」
2. 说「改到上午 10 点半」
```

预期：同一提醒被更新而非新增；到点后有站内 toast + 浏览器通知。

**④ 联网搜索**

```
说「搜索并总结 pgvector 适合记忆检索的三个原因」
```

预期：带来源引用的搜索结果，来源可信度分级。

**⑤ 明确遗忘**

```
说「忘记我的咖啡偏好」→ 再问咖啡推荐，AI 不再使用该偏好
```

### 可优化空间与后续链路

项目的可优化点、已知技术债和后续演进方向，详见 [`docs/current/06-roadmap.md`](docs/current/06-roadmap.md)，包括：

- **语义去重升级 embedding**：当前用词法相似度，后续可升级 bge-m3 embedding 处理近义不重叠表达
- **记忆演化历史展示 UI**：让用户在记忆页感知「此前为 X」的演化
- **MCP 工具接入**、**数据导出**、**首 token 体验优化**等长期方向

## 📖 文档

完整项目文档见 [`docs/current/`](docs/current/)：

| 文档 | 内容 |
|---|---|
| [项目介绍](docs/current/01-project-introduction.md) | 定位、背景、能力、技术栈 |
| [系统架构](docs/current/02-system-architecture.md) | 模块、拓扑、主 Agent-Subagent、数据流 |
| [技术实现](docs/current/03-technical-implementation.md) | 各模块实现细节 + 关键文件 |
| [功能场景](docs/current/04-features-scenarios.md) | 各能力的使用场景 |
| [体验流程](docs/current/05-experience-flow.md) | 用户操作路径 |
| [后续可优化点](docs/current/06-roadmap.md) | 长期方向 + 已知技术债 |
| [记忆检索优化](docs/current/07-memory-retrieval-optimization.md) | 检索评测 + 优化报告 |
| [部署指南](docs/DEPLOYMENT.md) | 环境要求 + 依赖迁移 + 密钥配置 |

设计期文档（Spec 驱动）见 `docs/` 和 `specs/`。

## 🧪 测试

```bash
make test              # 全部自动化测试（pytest 150 + vitest）
make ci                # 本地 CI 等价检查
make security-check    # 密钥扫描 + 依赖审计
make e2e               # 浏览器端到端（Playwright）
```

## 📁 项目结构

```
apps/
  api/          # 后端（FastAPI，模块化单体）
  web/          # 前端（Next.js）
packages/
  contracts/    # OpenAPI + TypeScript 契约
infra/          # Docker Compose、Dockerfile
scripts/        # 开发/检查/seed 脚本
specs/          # Spec 驱动实施文档
docs/           # 设计文档 + 现状文档
```

## 🔒 隐私与安全

- 密码 Argon2id 哈希，session + HttpOnly Cookie
- 所有数据 `user_id` 强制隔离，跨用户访问返回 404
- 日志脱敏（正文/密码/Token 只记长度）
- Prompt Injection 防护，SSRF 规避
- `.env` 已排除出 Git，密钥需自行配置（见 [部署指南](docs/DEPLOYMENT.md)）

## 📄 License

本项目为学习/答辩用途的个人项目。

## 🙏 致谢

- [DeepSeek](https://www.deepseek.com/) — 提供 LLM 能力
- [SearXNG](https://docs.searxng.org/) — 自建搜索
- [shadcn/ui](https://ui.shadcn.com/) — UI 组件库
- [pgvector](https://github.com/pgvector/pgvector) — 向量检索
