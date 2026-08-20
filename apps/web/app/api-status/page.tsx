import Link from "next/link";

import { ApiStatus } from "@/components/api-status";

const checks = [
  ["Web", "Next.js 页面与静态构建", "available"],
  ["API", "FastAPI 进程存活检查", "runtime"],
  ["Database", "PostgreSQL 与迁移状态", "planned"],
  ["Redis", "缓存与短期状态", "planned"],
] as const;

export default function ApiStatusPage() {
  return (
    <main className="min-h-screen bg-[#f4f6fb] px-6 py-12 text-slate-950">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="text-sm font-medium text-slate-500 hover:text-slate-900">
          ← 返回首页
        </Link>

        <div className="mt-8 rounded-3xl border border-slate-200 bg-white p-7 sm:p-9">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-indigo-600">
                Foundation status
              </p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">工程连通状态</h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">
                这里展示当前浏览器能够验证的基础服务状态。数据库和 Redis 将在基础设施子步骤完成后接入 ready 检查。
              </p>
            </div>
            <div className="rounded-full border border-slate-200 px-3 py-1.5">
              <ApiStatus />
            </div>
          </div>

          <div className="mt-8 divide-y divide-slate-100 border-y border-slate-100">
            {checks.map(([name, description, state]) => (
              <div key={name} className="flex items-center justify-between gap-4 py-4">
                <div>
                  <p className="text-sm font-semibold">{name}</p>
                  <p className="mt-1 text-sm text-slate-500">{description}</p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    state === "available"
                      ? "bg-emerald-50 text-emerald-700"
                      : state === "runtime"
                        ? "bg-indigo-50 text-indigo-700"
                        : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {state === "available"
                    ? "已就绪"
                    : state === "runtime"
                      ? "运行时检测"
                      : "下一子步骤"}
                </span>
              </div>
            ))}
          </div>

          <p className="mt-6 text-xs leading-5 text-slate-400">
            页面状态不等同于完整产品验收；真实结果以 SPEC-001 verification 记录为准。
          </p>
        </div>
      </div>
    </main>
  );
}
