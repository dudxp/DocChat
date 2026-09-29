export type SearchMode = "vector" | "hybrid";

export interface Health {
  status: string;
  provider: string;
  chat_model: string;
  embedding_model: string;
  search_mode: SearchMode;
  top_k: number;
}

export interface Area {
  id: number;
  name: string;
}

export interface User {
  id: number;
  username: string;
  name: string;
  is_admin: boolean;
  areas: Area[];
}

export interface UserInput {
  name: string;
  is_admin: boolean;
  area_ids: number[];
  password?: string;
}

export interface DocumentAccess {
  is_global: boolean;
  area_ids: number[];
}

export interface DocumentInfo {
  id: number;
  filename: string;
  num_pages: number;
  size_bytes: number;
  chunk_count: number;
  created_at: string;
  is_global: boolean;
  areas: Area[];
}

export interface UploadResult {
  documents: DocumentInfo[];
  errors: { filename: string; error: string }[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Source {
  number: number;
  document_id: number;
  filename: string;
  page: number;
  content: string;
  similarity: number;
  cited: boolean;
}

export interface ChatResponse {
  answer: string;
  search_query: string;
  sources: Source[];
  latency_ms: number;
}

export interface EvalCaseInput {
  question: string;
  expected_answer: string;
  document_id: number | null;
  expected_page: number | null;
}

export interface EvalCase extends EvalCaseInput {
  id: number;
  document_filename: string | null;
}

export interface EvalSummary {
  cases: number;
  hit_rate: number | null;
  mrr: number | null;
  citation_accuracy: number | null;
  answer_f1: number | null;
  judge_score: number | null;
  avg_latency_ms: number;
}

export interface EvalRun {
  id: number;
  created_at: string;
  config: {
    provider: string;
    chat_model: string;
    embedding_model: string;
    top_k: number;
    search_mode: SearchMode;
    judge: boolean;
  };
  summary: EvalSummary;
}

export interface EvalResult {
  id: number;
  question: string;
  expected_answer: string;
  expected_page: number | null;
  answer: string;
  retrieved: { filename: string; page: number; similarity: number }[];
  retrieval_hit: boolean | null;
  reciprocal_rank: number | null;
  citation_hit: boolean | null;
  answer_f1: number;
  judge_score: number | null;
  judge_reason: string | null;
  latency_ms: number;
}

export interface EvalRunDetail extends EvalRun {
  results: EvalResult[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

// --- Sessão ---

const TOKEN_KEY = "docchat-token";
let token: string | null = null;
try {
  token = localStorage.getItem(TOKEN_KEY);
} catch {
  /* storage indisponível: a sessão dura até fechar a aba */
}
let onUnauthorized: () => void = () => {};

export const session = {
  get token() {
    return token;
  },
  set(value: string | null) {
    token = value;
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* segue só em memória */
    }
  },
  /** Chamado quando a API responde 401 (token expirado ou inválido). */
  onUnauthorized(handler: () => void) {
    onUnauthorized = handler;
  },
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (response.status === 401 && token) {
    session.set(null);
    onUnauthorized();
  }
  if (!response.ok) {
    let message = `Erro ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail))
        message = body.detail.map((d: { error?: string; msg?: string }) => d.error ?? d.msg).join(" · ");
    } catch {
      /* resposta sem JSON */
    }
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/health"),

  login: (username: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username, password }),
    }),
  me: () => request<User>("/auth/me"),

  areas: () => request<Area[]>("/areas"),
  createArea: (name: string) => request<Area>("/areas", json("POST", { name })),
  renameArea: (id: number, name: string) => request<Area>(`/areas/${id}`, json("PUT", { name })),
  deleteArea: (id: number) => request<void>(`/areas/${id}`, { method: "DELETE" }),

  users: () => request<User[]>("/users"),
  createUser: (body: UserInput & { username: string; password: string }) =>
    request<User>("/users", json("POST", body)),
  updateUser: (id: number, body: UserInput) => request<User>(`/users/${id}`, json("PUT", body)),
  deleteUser: (id: number) => request<void>(`/users/${id}`, { method: "DELETE" }),

  documents: () => request<DocumentInfo[]>("/documents"),
  upload: (files: File[], access: DocumentAccess) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("is_global", String(access.is_global));
    access.area_ids.forEach((id) => form.append("area_ids", String(id)));
    return request<UploadResult>("/documents", { method: "POST", body: form });
  },
  updateAccess: (id: number, access: DocumentAccess) =>
    request<DocumentInfo>(`/documents/${id}/access`, json("PUT", access)),
  deleteDocument: (id: number) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  /** O PDF abre numa aba nova, que não manda cabeçalho; por isso o token vai na URL. */
  fileUrl: (id: number, page?: number) =>
    `/api/documents/${id}/file?access_token=${encodeURIComponent(token ?? "")}${page ? `#page=${page}` : ""}`,

  chat: (body: {
    question: string;
    history: ChatMessage[];
    document_ids?: number[] | null;
    top_k?: number;
    search_mode?: SearchMode;
  }) => request<ChatResponse>("/chat", json("POST", body)),

  cases: () => request<EvalCase[]>("/eval/cases"),
  createCase: (body: EvalCaseInput) => request<EvalCase>("/eval/cases", json("POST", body)),
  updateCase: (id: number, body: EvalCaseInput) => request<EvalCase>(`/eval/cases/${id}`, json("PUT", body)),
  deleteCase: (id: number) => request<void>(`/eval/cases/${id}`, { method: "DELETE" }),
  importCases: (items: unknown[]) =>
    request<{ imported: number; skipped: string[] }>("/eval/cases/import", json("POST", items)),
  exportCases: () => request<unknown[]>("/eval/cases/export"),

  runs: () => request<EvalRun[]>("/eval/runs"),
  run: (id: number) => request<EvalRunDetail>(`/eval/runs/${id}`),
  createRun: (body: { top_k?: number; search_mode?: SearchMode; use_judge: boolean }) =>
    request<EvalRunDetail>("/eval/runs", json("POST", body)),
  deleteRun: (id: number) => request<void>(`/eval/runs/${id}`, { method: "DELETE" }),
};
