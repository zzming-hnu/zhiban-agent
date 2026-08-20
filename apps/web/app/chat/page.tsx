"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookMarked,
  Check,
  ChevronDown,
  ListTodo,
  LogOut,
  MessageSquarePlus,
  Sparkles,
  Trash2,
  Loader2,
  Send,
  Wrench,
} from "lucide-react";

import { Markdown } from "@/components/markdown";
import {
  chatStream,
  createConversation,
  deleteConversation,
  getMe,
  listConversations,
  listMessages,
  listModels,
  logout,
  type ConversationResponse,
  type ModelView,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

interface ToolCallView {
  tool: string;
  args?: Record<string, unknown>;
  summary: string;
  ok: boolean;
}

interface DisplayMessage {
  id: string;
  role: string;
  content: string;
  status: string;
  thinking?: boolean;
  toolCalls?: ToolCallView[];
}

export default function ChatPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ display_name: string; email: string } | null>(null);
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [models, setModels] = useState<ModelView[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [deletingConv, setDeletingConv] = useState<ConversationResponse | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const selectConversation = useCallback(async (id: string) => {
    setActiveConvId(id);
    const msgs = await listMessages(id);
    setMessages(msgs.map((m) => ({ ...m })));
  }, []);

  const loadConversations = useCallback(async () => {
    const convs = await listConversations();
    setConversations(convs);
    if (convs.length > 0 && !activeConvId) {
      selectConversation(convs[0].id);
    }
  }, [activeConvId, selectConversation]);

  useEffect(() => {
    getMe().then((me) => {
      if (!me) {
        router.push("/login");
      } else {
        setUser(me);
        loadConversations();
      }
    });
  }, [router, loadConversations]);

  useEffect(() => {
    listModels()
      .then((res) => {
        setModels(res.data);
        setSelectedModel(res.default || res.data[0]?.id || "");
      })
      .catch(() => {
        setModels([]);
      });
  }, []);

  async function confirmDeleteConversation() {
    if (!deletingConv) return;
    const id = deletingConv.id;
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConvId === id) {
        setActiveConvId(null);
        setMessages([]);
      }
    } catch {
      // ignore; keep the dialog closed
    } finally {
      setDeletingConv(null);
    }
  }

  async function handleNewConversation() {
    const conv = await createConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveConvId(conv.id);
    setMessages([]);
  }

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  async function handleSend() {
    if (!input.trim() || isStreaming || !activeConvId) return;

    const userContent = input.trim();
    setInput("");
    setIsStreaming(true);

    const userMsg: DisplayMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: userContent,
      status: "completed",
    };
    const assistantMsg: DisplayMessage = {
      id: `temp-assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      status: "generating",
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    abortRef.current = chatStream(
      activeConvId,
      userContent,
      (delta) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + delta,
            };
          }
          return updated;
        });
      },
      () => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = { ...last, status: "completed" };
          }
          return updated;
        });
        setIsStreaming(false);
        loadConversations();
      },
      (err) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: last.content || `发生错误: ${err}`,
              status: "failed",
            };
          }
          return updated;
        });
        setIsStreaming(false);
      },
      (tool, args) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            const toolCalls = last.toolCalls || [];
            updated[updated.length - 1] = {
              ...last,
              toolCalls: [...toolCalls, { tool, args, summary: "执行中...", ok: true }],
            };
          }
          return updated;
        });
      },
      (tool, summary, ok) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant" && last.toolCalls) {
            const toolCalls = [...last.toolCalls];
            const idx = toolCalls.findIndex((tc) => tc.tool === tool && tc.summary === "执行中...");
            if (idx >= 0) {
              toolCalls[idx] = { ...toolCalls[idx], summary, ok };
            }
            updated[updated.length - 1] = { ...last, toolCalls };
          }
          return updated;
        });
      },
      selectedModel,
      () => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = { ...last, thinking: true };
          }
          return updated;
        });
      },
    );
  }

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const selectedModelLabel =
    models.find((m) => m.id === selectedModel)?.label || selectedModel || "选择模型";

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="flex w-72 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-3 border-b border-border px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-semibold">{user.display_name}</p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
          </div>
        </div>

        <div className="px-3 py-3">
          <Button className="w-full" onClick={handleNewConversation}>
            <MessageSquarePlus className="h-4 w-4" />
            新对话
          </Button>
        </div>

        <ScrollArea className="flex-1 px-3">
          <div className="space-y-1 pb-2">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => selectConversation(conv.id)}
                className={`group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition ${
                  activeConvId === conv.id
                    ? "bg-secondary font-medium text-foreground"
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                }`}
              >
                <span className="flex-1 truncate">{conv.title}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="hidden h-6 w-6 group-hover:flex"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeletingConv(conv);
                  }}
                  title="删除对话"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="border-t border-border px-3 py-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="mb-2 w-full justify-between">
                <span className="truncate">{selectedModelLabel}</span>
                <ChevronDown className="h-4 w-4 opacity-50" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {models.map((model) => (
                <DropdownMenuItem
                  key={model.id}
                  onClick={() => setSelectedModel(model.id)}
                >
                  <span className="flex-1">{model.label}</span>
                  {selectedModel === model.id && <Check className="h-4 w-4" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <Button variant="ghost" className="w-full justify-start" onClick={() => router.push("/memories")}>
            <BookMarked className="h-4 w-4" />
            我的记忆
          </Button>
          <Button variant="ghost" className="w-full justify-start" onClick={() => router.push("/todos")}>
            <ListTodo className="h-4 w-4" />
            待办与提醒
          </Button>
          <Separator className="my-2" />
          <Button
            variant="ghost"
            className="w-full justify-start text-muted-foreground"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />
            退出登录
          </Button>
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex flex-1 flex-col">
        {activeConvId ? (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-6">
              <div className="mx-auto max-w-3xl space-y-4">
                {messages.length === 0 && (
                  <div className="py-20 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary">
                      <Sparkles className="h-7 w-7 text-muted-foreground" />
                    </div>
                    <p className="text-lg font-medium text-foreground">开始新对话</p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      试着说「你好」或者问我任何问题
                    </p>
                  </div>
                )}
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                        msg.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "border border-border bg-card text-foreground"
                      }`}
                    >
                      {msg.toolCalls && msg.toolCalls.length > 0 && (
                        <div className="mb-2 space-y-1.5">
                          {msg.toolCalls.map((tc, i) => (
                            <div
                              key={i}
                              className={`rounded-lg px-2.5 py-1.5 text-xs ${
                                tc.ok
                                  ? "bg-emerald-50 text-emerald-700"
                                  : "bg-rose-50 text-rose-700"
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                {tc.summary === "执行中..." ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Wrench className="h-3 w-3" />
                                )}
                                <Badge variant={tc.ok ? "success" : "destructive"}>
                                  {tc.tool}
                                </Badge>
                                <span className="truncate">{tc.summary}</span>
                              </div>
                              {tc.args && Object.keys(tc.args).length > 0 && (
                                <div className="mt-1 truncate font-mono text-[11px] opacity-70">
                                  {JSON.stringify(tc.args)}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      {msg.role === "assistant" ? (
                        <Markdown content={msg.content} />
                      ) : (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      )}
                      {msg.status === "generating" && !msg.content && (
                        <span className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          思考中...
                        </span>
                      )}
                      {msg.status === "generating" && msg.content && (
                        <span className="mt-1 inline-block h-4 w-1 animate-pulse bg-primary/60 align-middle" />
                      )}
                      {msg.status === "failed" && (
                        <p className="mt-2 text-xs text-destructive">生成失败</p>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input */}
            <div className="border-t border-border bg-card px-6 py-4">
              <div className="mx-auto max-w-3xl">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="flex items-end gap-3"
                >
                  <Textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      // IME（中文输入法）组合期间，Enter 用于确认候选词，
                      // 不应触发提交。isComposing / keyCode 229 是组合状态的标志。
                      if (e.nativeEvent.isComposing || e.keyCode === 229) {
                        return;
                      }
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="输入消息（Enter 发送，Shift+Enter 换行）..."
                    rows={1}
                    className="max-h-40 min-h-10 flex-1 resize-none"
                    disabled={isStreaming}
                  />
                  <Button type="submit" disabled={isStreaming || !input.trim()} size="lg">
                    {isStreaming ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        生成中
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4" />
                        发送
                      </>
                    )}
                  </Button>
                </form>
                <p className="mt-2 text-center text-xs text-muted-foreground">
                  知伴可能会犯错，请核实重要信息
                </p>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <p className="text-lg font-medium text-foreground">选择或创建一个对话</p>
              <Button onClick={handleNewConversation} className="mt-4" size="lg">
                <MessageSquarePlus className="h-4 w-4" />
                开始新对话
              </Button>
            </div>
          </div>
        )}
      </main>

      <Dialog
        open={deletingConv !== null}
        onOpenChange={(open) => !open && setDeletingConv(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除对话</DialogTitle>
            <DialogDescription>确定删除这个对话吗？此操作无法撤销。</DialogDescription>
          </DialogHeader>
          <div className="rounded-md bg-muted px-3 py-2 text-sm text-foreground">
            {deletingConv?.title}
          </div>
          <Separator />
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingConv(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmDeleteConversation}>
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
