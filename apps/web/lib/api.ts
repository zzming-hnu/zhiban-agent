const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export interface UserView {
  id: string;
  email: string;
  display_name: string;
}

export interface SessionView {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent_hash: string | null;
}

export interface AuthResponse {
  user: UserView;
  session: SessionView;
}

export interface ConversationResponse {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationPage {
  data: ConversationResponse[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface MessageResponse {
  id: string;
  role: string;
  content: string;
  status: string;
  created_at: string;
}

export interface MessagePage {
  data: MessageResponse[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface MemoryView {
  id: string;
  memory_type: string;
  category: string;
  subject: string;
  predicate: string;
  value: string;
  content: string;
  source_kind: string;
  status: string;
  confidence: number;
  importance: number;
  evidence_quote: string;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface MemoryPage {
  data: MemoryView[];
  next_cursor: string | null;
  has_more: boolean;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  // Attach the double-submit CSRF token to state-changing requests.
  if (init?.method && !["GET", "HEAD", "OPTIONS"].includes(init.method)) {
    const csrf = readCookie("zhiban_csrf");
    if (csrf) {
      headers["X-CSRF-Token"] = csrf;
    }
  }
  return fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" });
}

export async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<AuthResponse> {
  const res = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName || "" }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.error?.message || "注册失败");
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.error?.message || "登录失败");
  }
  return res.json();
}

export interface ModelView {
  id: string;
  label: string;
}

export interface ModelsResponse {
  data: ModelView[];
  default: string;
}

export async function listModels(): Promise<ModelsResponse> {
  const res = await apiFetch("/models");
  if (!res.ok) throw new Error("获取模型列表失败");
  return res.json();
}

export async function getMe(): Promise<UserView | null> {
  try {
    const res = await apiFetch("/auth/me");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}

export async function listMemories(): Promise<MemoryView[]> {
  const res = await apiFetch("/memories");
  if (!res.ok) throw new Error("获取记忆列表失败");
  const page: MemoryPage = await res.json();
  return page.data;
}

export async function createMemory(body: {
  memory_type: string;
  category: string;
  subject: string;
  predicate: string;
  value: string;
}): Promise<MemoryView> {
  const res = await apiFetch("/memories", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("创建记忆失败");
  return res.json();
}

export async function updateMemory(
  memoryId: string,
  body: { value?: string; category?: string; importance?: number },
): Promise<MemoryView> {
  const res = await apiFetch(`/memories/${memoryId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("更新记忆失败");
  return res.json();
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const res = await apiFetch(`/memories/${memoryId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("删除记忆失败");
}

export interface TodoView {
  id: string;
  title: string;
  detail: string;
  status: string;
  due_at: string | null;
  priority: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ReminderView {
  id: string;
  title: string;
  remind_at: string;
  timezone: string;
  status: string;
  delivery_status: string;
  delivered_at: string | null;
  created_at: string;
}

export async function listTodos(): Promise<TodoView[]> {
  const res = await apiFetch("/todos");
  if (!res.ok) throw new Error("获取待办失败");
  return res.json();
}

export async function createTodo(title: string): Promise<TodoView> {
  const res = await apiFetch("/todos", {
    method: "POST",
    body: JSON.stringify({ title, timezone: "Asia/Shanghai" }),
  });
  if (!res.ok) throw new Error("创建待办失败");
  return res.json();
}

export async function completeTodo(todoId: string): Promise<TodoView> {
  const res = await apiFetch(`/todos/${todoId}/complete`, { method: "POST" });
  if (!res.ok) throw new Error("完成待办失败");
  return res.json();
}

export async function cancelTodo(todoId: string): Promise<void> {
  const res = await apiFetch(`/todos/${todoId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("取消待办失败");
}

export async function listReminders(): Promise<ReminderView[]> {
  const res = await apiFetch("/reminders");
  if (!res.ok) throw new Error("获取提醒失败");
  return res.json();
}

export async function cancelReminder(reminderId: string): Promise<void> {
  const res = await apiFetch(`/reminders/${reminderId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("取消提醒失败");
}

export async function pendingReminderNotifications(): Promise<ReminderView[]> {
  const res = await apiFetch("/reminders/pending-notifications");
  if (!res.ok) return [];
  return res.json();
}

export async function markReminderNotified(reminderId: string): Promise<void> {
  await apiFetch(`/reminders/${reminderId}/notified`, { method: "POST" });
}

export async function listConversations(): Promise<ConversationResponse[]> {
  const res = await apiFetch("/conversations");
  if (!res.ok) throw new Error("获取会话列表失败");
  const page: ConversationPage = await res.json();
  return page.data;
}

export async function createConversation(title?: string): Promise<ConversationResponse> {
  const res = await apiFetch("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: title || "新对话" }),
  });
  if (!res.ok) throw new Error("创建会话失败");
  return res.json();
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await apiFetch(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) throw new Error("删除会话失败");
}

export async function listMessages(conversationId: string): Promise<MessageResponse[]> {
  const res = await apiFetch(`/conversations/${conversationId}/messages`);
  if (!res.ok) throw new Error("获取消息失败");
  const page: MessagePage = await res.json();
  return page.data;
}

export interface RunAccepted {
  message_id: string;
  assistant_message_id: string;
  run_id: string;
  status: string;
  stream_url: string;
}

interface StreamEventPayload {
  seq: number;
  run_id: string;
  data: Record<string, unknown>;
  error?: { code?: string; message?: string };
}

export function chatStream(
  conversationId: string,
  content: string,
  onDelta: (text: string) => void,
  onComplete: () => void,
  onError: (err: string) => void,
  onToolStart?: (tool: string, args: Record<string, unknown>) => void,
  onToolComplete?: (tool: string, summary: string, ok: boolean) => void,
  model?: string,
  onThinking?: (round: number) => void,
): AbortController {
  const controller = new AbortController();

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const csrf = readCookie("zhiban_csrf");
  if (csrf) headers["X-CSRF-Token"] = csrf;

  async function run(): Promise<void> {
    // Phase 1: create the message + run.
    let runAccepted: RunAccepted;
    try {
      const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
        method: "POST",
        headers,
        body: JSON.stringify({ content, model }),
        signal: controller.signal,
        credentials: "include",
      });
      if (!res.ok) {
        const errBody = await res.text().catch(() => "(no body)");
        onError(`请求失败 ${res.status}: ${errBody.slice(0, 200)}`);
        return;
      }
      runAccepted = (await res.json()) as RunAccepted;
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError((err as Error).message);
      }
      return;
    }

    // Phase 2: consume the SSE stream.
    try {
      const streamRes = await fetch(`${API_BASE}${runAccepted.stream_url}`, {
        method: "GET",
        signal: controller.signal,
        credentials: "include",
      });
      if (!streamRes.ok || !streamRes.body) {
        const errBody = await streamRes.text().catch(() => "(no body)");
        onError(`流式请求失败 ${streamRes.status}: ${errBody.slice(0, 200)}`);
        return;
      }
      const reader = streamRes.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const raw = line.slice(6).trim();
            if (!raw) continue;
            let payload: StreamEventPayload | null = null;
            try {
              payload = JSON.parse(raw) as StreamEventPayload;
            } catch {
              payload = null;
            }

            if (currentEvent === "message.delta") {
              const delta = payload?.data?.delta;
              if (typeof delta === "string") onDelta(delta);
            } else if (currentEvent === "agent.thinking" && onThinking) {
              const round = payload?.data?.round;
              if (typeof round === "number") onThinking(round);
            } else if (currentEvent === "tool.call.started" && onToolStart) {
              const tool = payload?.data?.tool_name;
              if (typeof tool === "string") {
                const args = payload?.data?.arguments;
                onToolStart(tool, (args && typeof args === "object" ? args : {}) as Record<string, unknown>);
              }
            } else if (currentEvent === "tool.call.completed" && onToolComplete && payload) {
              const tool = payload.data.tool_name;
              if (typeof tool === "string") {
                onToolComplete(tool, String(payload.data.summary ?? ""), true);
              }
            } else if (currentEvent === "tool.call.failed" && onToolComplete && payload) {
              const tool = payload.data.tool_name;
              if (typeof tool === "string") {
                onToolComplete(tool, String(payload.data.summary ?? ""), false);
              }
            } else if (currentEvent === "message.completed") {
              onComplete();
            } else if (currentEvent === "run.failed") {
              onError(payload?.error?.message || "生成失败，请重试");
            }
          }
        }
      }
      onComplete();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError((err as Error).message);
      }
    }
  }

  void run();
  return controller;
}
