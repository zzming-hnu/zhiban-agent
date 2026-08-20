import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Toaster } from "sonner";

import { ReminderToast } from "@/components/reminder-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "知伴 · 个人 AI 助理",
  description: "一个具备可控记忆和可靠工具能力的个人 AI 助理",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        {children}
        <ReminderToast />
        <Toaster position="top-center" richColors />
      </body>
    </html>
  );
}
