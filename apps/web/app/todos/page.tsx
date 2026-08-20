"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Bell, CheckCircle2, Circle, ListTodo, Plus, Trash2 } from "lucide-react";

import {
  cancelReminder,
  cancelTodo,
  completeTodo,
  createTodo,
  getMe,
  listReminders,
  listTodos,
  type ReminderView,
  type TodoView,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

type DeleteTarget = { kind: "todo" | "reminder"; id: string; title: string } | null;

export default function TodosPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ display_name: string } | null>(null);
  const [todos, setTodos] = useState<TodoView[]>([]);
  const [reminders, setReminders] = useState<ReminderView[]>([]);
  const [newTitle, setNewTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<DeleteTarget>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMe().then((me) => {
      if (!me) {
        router.push("/login");
      } else {
        setUser(me);
        void load();
      }
    });
  }, [router]);

  async function load() {
    setLoading(true);
    try {
      const [t, r] = await Promise.all([listTodos(), listReminders()]);
      setTodos(t);
      setReminders(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTodo() {
    if (!newTitle.trim()) return;
    try {
      await createTodo(newTitle.trim());
      setNewTitle("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    }
  }

  async function handleComplete(id: string) {
    try {
      await completeTodo(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    try {
      if (deleting.kind === "todo") {
        await cancelTodo(deleting.id);
      } else {
        await cancelReminder(deleting.id);
      }
      setDeleting(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
      setDeleting(null);
    }
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  const pendingTodos = todos.filter((t) => t.status === "pending");
  const doneTodos = todos.filter((t) => t.status === "done");

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <ListTodo className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold">待办与提醒</p>
              <p className="text-xs text-muted-foreground">把对话里的行动项变成可追踪的任务</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => router.push("/chat")}>
            <ArrowLeft className="h-4 w-4" />
            返回对话
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        {error && (
          <p className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {/* 新建待办 */}
        <div className="mb-8 flex gap-2">
          <Input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              // IME 组合期间 Enter 用于确认候选词，不触发提交。
              if (e.nativeEvent.isComposing || e.keyCode === 229) return;
              if (e.key === "Enter") handleCreateTodo();
            }}
            placeholder="添加一个待办..."
            className="h-10"
          />
          <Button onClick={handleCreateTodo} className="h-10">
            <Plus className="h-4 w-4" />
            添加
          </Button>
        </div>

        {/* 提醒 */}
        <section className="mb-8">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold">提醒</h2>
            <Badge variant="secondary">{reminders.length}</Badge>
          </div>
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : reminders.length === 0 ? (
            <p className="rounded-xl border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
              暂无提醒。在对话里说「明天9点提醒我…」即可创建。
            </p>
          ) : (
            <div className="space-y-2">
              {reminders.map((r) => (
                <Card key={r.id} className="gap-3 py-3">
                  <CardContent className="flex items-center justify-between gap-4 px-4">
                    <div className="flex flex-1 items-center gap-3">
                      <Bell className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm text-foreground">{r.title}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {new Date(r.remind_at).toLocaleString("zh-CN")} · {r.timezone}
                        </p>
                      </div>
                      {r.status === "delivered" && <Badge variant="success">已提醒</Badge>}
                    </div>
                    {r.status !== "cancelled" && r.status !== "delivered" && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() =>
                          setDeleting({ kind: "reminder", id: r.id, title: r.title })
                        }
                        title="取消提醒"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>

        {/* 待办 */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold">待办</h2>
            <Badge variant="secondary">
              {pendingTodos.length} 进行中 · {doneTodos.length} 已完成
            </Badge>
          </div>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : todos.length === 0 ? (
            <p className="rounded-xl border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
              暂无待办。在对话里说「帮我记个待办」即可创建。
            </p>
          ) : (
            <div className="space-y-2">
              {todos.map((t) => {
                const done = t.status === "done";
                return (
                  <Card key={t.id} className="gap-3 py-3">
                    <CardContent className="flex items-center justify-between gap-4 px-4">
                      <div className="flex flex-1 items-center gap-3">
                        <button
                          type="button"
                          onClick={() => !done && handleComplete(t.id)}
                          className="shrink-0 text-muted-foreground transition-colors hover:text-primary"
                          title={done ? "已完成" : "标记完成"}
                        >
                          {done ? (
                            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                          ) : (
                            <Circle className="h-5 w-5" />
                          )}
                        </button>
                        <div className="flex-1">
                          <p
                            className={`text-sm ${
                              done ? "text-muted-foreground line-through" : "text-foreground"
                            }`}
                          >
                            {t.title}
                          </p>
                          {t.due_at && (
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              截止：{new Date(t.due_at).toLocaleString("zh-CN")}
                            </p>
                          )}
                        </div>
                      </div>
                      {!done && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleting({ kind: "todo", id: t.id, title: t.title })}
                          title="取消待办"
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>
      </main>

      <Dialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{deleting?.kind === "reminder" ? "取消提醒" : "取消待办"}</DialogTitle>
            <DialogDescription>
              {deleting?.kind === "reminder"
                ? "确定取消这个提醒吗？"
                : "确定取消这个待办吗？"}
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md bg-muted px-3 py-2 text-sm text-foreground">
            {deleting?.title}
          </div>
          <Separator />
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              再想想
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              确定
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
