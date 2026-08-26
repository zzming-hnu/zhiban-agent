import Link from "next/link";

import { ApiStatus } from "@/components/api-status";

const capabilities = [
  {
    index: "01",
    title: "连续对话",
    description: "保留近期上下文，用流式响应让每次交流自然衔接。",
    status: "已可体验",
  },
  {
    index: "02",
    title: "可控记忆",
    description: "记住真正重要的信息，也允许你查看、更正与遗忘。",
    status: "已可体验",
  },
  {
    index: "03",
    title: "可靠工具",
    description: "检索、摘要和任务操作都有明确状态与失败兜底。",
    status: "已可体验",
  },
  {
    index: "04",
    title: "任务跟踪",
    description: "把对话里的行动项变成可查询、可更新的真实任务。",
    status: "已可体验",
  },
] as const;

export default function Home() {
  return (
    <div className="min-h-screen bg-[#f4f6fb] text-slate-950">
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-sm font-semibold text-white">
              知
            </div>
            <div>
              <p className="text-base font-semibold tracking-tight">知伴</p>
              <p className="text-xs text-slate-500">你的个人 AI 助理</p>
            </div>
          </div>
          <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5">
            <ApiStatus />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-12 lg:px-10 lg:py-20">
        <section className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
              核心能力已上线
            </div>
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-[-0.035em] text-slate-950 sm:text-5xl lg:text-6xl">
              把每次对话，
              <br />
              变成可以延续的理解。
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
              知伴会记住你允许保存的信息，可靠地调用工具，并让每个任务都有真实状态。现在就可以开始体验。
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/chat"
                className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                开始对话
              </Link>
              <Link
                href="/login"
                className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
              >
                登录 / 注册
              </Link>
            </div>
          </div>

          <div className="relative rounded-[28px] border border-slate-200 bg-white p-5">
            <div className="absolute -right-5 -top-5 h-24 w-24 rounded-full bg-indigo-100 blur-2xl" />
            <div className="relative rounded-2xl bg-slate-950 p-6 text-white">
              <div className="mb-10 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white">构建进度</p>
                  <p className="mt-1 text-xs text-slate-400">核心能力已全部落地</p>
                </div>
                <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">
                  complete
                </span>
              </div>
              <div className="space-y-5">
                <div>
                  <div className="mb-2 flex justify-between text-xs">
                    <span className="text-slate-300">规格与工具链</span>
                    <span className="text-emerald-300">完成</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/10">
                    <div className="h-full w-full rounded-full bg-emerald-400" />
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex justify-between text-xs">
                    <span className="text-slate-300">Web / API / Worker</span>
                    <span className="text-emerald-300">完成</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/10">
                    <div className="h-full w-full rounded-full bg-emerald-400" />
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex justify-between text-xs">
                    <span className="text-slate-300">对话 · 记忆 · 工具 · 任务</span>
                    <span className="text-emerald-300">完成</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/10">
                    <div className="h-full w-full rounded-full bg-emerald-400" />
                  </div>
                </div>
              </div>
              <div className="mt-10 border-t border-white/10 pt-5">
                <p className="text-sm leading-6 text-slate-300">
                  多轮对话、可控记忆、可靠工具与任务跟踪，已可完整体验。
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-20">
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-indigo-600">
                Core capabilities
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight">四个可靠能力，已经可以体验</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-slate-500">
              每一能力都经过设计、实现与测试，从对话、记忆到工具与任务，形成一条完整可验证的体验链路。
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {capabilities.map((capability) => (
              <article
                key={capability.index}
                className="rounded-2xl border border-slate-200 bg-white p-5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-slate-400">{capability.index}</span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                    {capability.status}
                  </span>
                </div>
                <h3 className="mt-8 text-lg font-semibold">{capability.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{capability.description}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
