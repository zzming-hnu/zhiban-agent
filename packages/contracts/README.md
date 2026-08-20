# 共享契约

该目录保存由 FastAPI OpenAPI 生成的 TypeScript 契约。

禁止手工复制一套与 Pydantic 模型独立演进的接口类型。

## 文件

- `openapi.json`：由 FastAPI `app.openapi()` 确定性导出。
- `src/api.ts`：由 `openapi-typescript` 生成，禁止手工编辑。
- `src/index.ts`：稳定导出入口。

## 命令

从仓库根目录运行：

```bash
make contracts
make contracts-check
```

`contracts-check` 在临时目录重新生成两个文件并逐字节比较，不依赖 Git 仓库。
