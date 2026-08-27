"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Pencil, Trash2, BookMarked } from "lucide-react";

import {
  deleteMemory,
  getMe,
  listMemories,
  updateMemory,
  type MemoryView,
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
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

const CATEGORY_LABELS: Record<string, string> = {
  basic_info: "基本信息",
  communication_taboo: "沟通禁忌",
  communication_preference: "沟通偏好",
  other: "其他",
};

const CATEGORY_ORDER = [
  "basic_info",
  "communication_taboo",
  "communication_preference",
  "other",
];

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

export default function MemoriesPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ display_name: string } | null>(null);
  const [memories, setMemories] = useState<MemoryView[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editCategory, setEditCategory] = useState("other");
  const [deleting, setDeleting] = useState<MemoryView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMe().then((me) => {
      if (!me) {
        router.push("/login");
      } else {
        setUser(me);
        void loadMemories();
      }
    });
  }, [router]);

  async function loadMemories() {
    setLoading(true);
    try {
      setMemories(await listMemories());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  function groupByCategory(items: MemoryView[]): Record<string, MemoryView[]> {
    const groups: Record<string, MemoryView[]> = {};
    for (const cat of CATEGORY_ORDER) {
      groups[cat] = items.filter((m) => m.category === cat);
    }
    const known = new Set(CATEGORY_ORDER);
    groups["other"] = groups["other"].concat(items.filter((m) => !known.has(m.category)));
    return groups;
  }

  function startEdit(m: MemoryView) {
    setEditingId(m.id);
    setEditValue(m.value);
    setEditCategory(m.category);
  }

  async function saveEdit(m: MemoryView) {
    try {
      await updateMemory(m.id, { value: editValue, category: editCategory });
      setEditingId(null);
      await loadMemories();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    try {
      await deleteMemory(deleting.id);
      setDeleting(null);
      await loadMemories();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
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

  const groups = groupByCategory(memories);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <BookMarked className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold">我的记忆</p>
              <p className="text-xs text-muted-foreground">知伴记住的、关于你的信息</p>
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

        {loading ? (
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-16 w-full" />
              </div>
            ))}
          </div>
        ) : memories.length === 0 ? (
          <div className="rounded-xl border border-border bg-card py-16 text-center">
            <BookMarked className="mx-auto mb-4 h-10 w-10 text-muted-foreground/40" />
            <p className="text-foreground">还没有保存任何记忆</p>
            <p className="mt-2 text-sm text-muted-foreground">
              在对话中告诉知伴「记住…」，它会帮你整理到这里
            </p>
          </div>
        ) : (
          <Tabs defaultValue="basic_info">
            <TabsList className="mb-6 flex-wrap">
              {CATEGORY_ORDER.map((cat) => (
                <TabsTrigger key={cat} value={cat} className="gap-1.5">
                  {CATEGORY_LABELS[cat]}
                  <Badge variant="secondary" className="h-5 min-w-5 px-1.5">
                    {groups[cat]?.length ?? 0}
                  </Badge>
                </TabsTrigger>
              ))}
            </TabsList>

            {CATEGORY_ORDER.map((cat) => {
              const items = groups[cat] ?? [];
              return (
                <TabsContent key={cat} value={cat}>
                  {items.length === 0 ? (
                    <div className="rounded-xl border border-border bg-card py-12 text-center">
                      <p className="text-sm text-muted-foreground">
                        这一分类还没有记忆
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {items.map((m) => (
                        <Card key={m.id} className="gap-3 py-3">
                          <CardContent className="px-4">
                            {editingId === m.id ? (
                              <div className="space-y-2">
                                <Textarea
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  rows={2}
                                />
                                <div className="flex items-center justify-between">
                                  <Select value={editCategory} onValueChange={setEditCategory}>
                                    <SelectTrigger className="w-40">
                                      {CATEGORY_LABELS[editCategory]}
                                    </SelectTrigger>
                                    <SelectContent>
                                      {CATEGORY_ORDER.map((c) => (
                                        <SelectItem key={c} value={c}>
                                          {CATEGORY_LABELS[c]}
                                        </SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                  <div className="flex gap-2">
                                    <Button size="sm" onClick={() => saveEdit(m)}>
                                      保存
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setEditingId(null)}
                                    >
                                      取消
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1">
                                  <p className="text-sm text-foreground">{m.content}</p>
                                  <div className="mt-2 flex items-center gap-3">
                                    <span className="text-xs text-muted-foreground">
                                      来源：
                                      {m.source_kind === "explicit" ? "明确要求" : "自动提取"}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                      更新于 {formatTime(m.updated_at)}
                                    </span>
                                  </div>
                                </div>
                                <div className="flex shrink-0 gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => startEdit(m)}
                                    title="编辑"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setDeleting(m)}
                                    title="删除"
                                    className="text-destructive hover:text-destructive"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </div>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </TabsContent>
              );
            })}
          </Tabs>
        )}
      </main>

      <Dialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除记忆</DialogTitle>
            <DialogDescription>
              确定删除这条记忆吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md bg-muted px-3 py-2 text-sm text-foreground">
            {deleting?.content}
          </div>
          <Separator />
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
