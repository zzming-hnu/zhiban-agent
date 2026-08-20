# 知伴 Web

Next.js、React、TypeScript 和 Tailwind CSS 构成的 Web 应用。

## 当前范围

- 产品基础展示页。
- API 存活状态检测。
- `/api-status` 工程状态页。
- Vitest + Testing Library 基础测试。

登录、会话、聊天和记忆功能将在后续 Spec 中实现。

## 命令

从仓库根目录运行：

```bash
make dev-web
make lint
make typecheck
make test
make build
```

或仅在当前目录运行：

```bash
corepack pnpm dev
```

访问 [http://localhost:3000](http://localhost:3000)。

浏览器只允许读取 `NEXT_PUBLIC_` 前缀环境变量。模型密钥、数据库 URL 和 Session Secret 禁止进入 Web 配置。
