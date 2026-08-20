"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("web_route_error", {
      name: error.name,
      digest: error.digest,
    });
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f4f6fb] px-6">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-rose-600">
          Something went wrong
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
          页面暂时无法显示
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          你的数据没有被标记为成功处理。可以重试当前页面，或返回后稍后再试。
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-6 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white"
        >
          重试
        </button>
      </div>
    </main>
  );
}
