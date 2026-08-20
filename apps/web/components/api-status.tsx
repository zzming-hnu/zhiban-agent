"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "online" | "offline";

const labels: Record<Status, string> = {
  checking: "正在检查 API",
  online: "API 已连接",
  offline: "API 尚未启动",
};

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const controller = new AbortController();
    const baseUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

    async function checkHealth() {
      try {
        const response = await fetch(`${baseUrl}/health/live`, {
          cache: "no-store",
          signal: controller.signal,
        });
        setStatus(response.ok ? "online" : "offline");
      } catch {
        if (!controller.signal.aborted) {
          setStatus("offline");
        }
      }
    }

    void checkHealth();
    return () => controller.abort();
  }, []);

  return (
    <div className="flex items-center gap-2" aria-live="polite">
      <span
        className={`h-2 w-2 rounded-full ${
          status === "online"
            ? "bg-emerald-500"
            : status === "checking"
              ? "animate-pulse bg-amber-400"
              : "bg-slate-300"
        }`}
        aria-hidden="true"
      />
      <span className="text-sm font-medium text-slate-600">{labels[status]}</span>
    </div>
  );
}
