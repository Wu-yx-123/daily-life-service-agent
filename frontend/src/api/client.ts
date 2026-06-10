// 作用：封装前端访问 Phase 1 FastAPI 接口的请求函数。
import type {
  AgentRunResponse,
  AfterSalesTicket,
  ApprovalDecisionResponse,
  ApprovalListItem,
  ConversationResponse,
  KnowledgeAnswer,
  LocationInput,
  OpsReport,
  OrderConfirmResponse,
  ReviewAnalyzeResponse,
  StoreRecommendationResponse
} from "../types/agent";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function getAuthToken() {
  try {
    const saved = sessionStorage.getItem("massageops_user");
    return saved ? JSON.parse(saved)?.access_token : null;
  } catch {
    return null;
  }
}

// 统一封装 fetch，后续加鉴权、错误追踪时只需要改这里。
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  // Vite 开发环境下 API_BASE 为空时，会走 vite.config.ts 中的 /api 代理。
  const isFormData = options?.body instanceof FormData;
  const headers = isFormData
    ? { ...(options?.headers ?? {}) }
    : { "Content-Type": "application/json", ...(options?.headers ?? {}) };
  const token = getAuthToken();
  if (token) {
    (headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  });
  if (!response.ok) {
    // 保留后端返回的错误文本，方便页面直接显示失败原因。
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function login(payload: { username: string; password: string; login_as: "customer" | "merchant" }) {
  return request<any>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// 发送自然语言预约消息，后端返回候选预约方案或追问。
export function sendMessage(payload: { session_id: string; user_id: string; message: string }) {
  return request<ConversationResponse>("/api/v1/conversations/message", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// 用户确认候选方案后创建正式订单。
export function confirmOrder(payload: { trace_id: string; option_id: string; user_confirmed: boolean }) {
  return request<OrderConfirmResponse>("/api/v1/orders/confirm", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// 查询 Agent Trace，聊天页右侧时间线使用。
export function fetchAgentRun(traceId: string) {
  return request<AgentRunResponse>(`/api/v1/agent-runs/${traceId}`);
}

// 查询人工审批单，Phase 2 平台运营端使用。
export function fetchApprovals(status = "pending") {
  return request<ApprovalListItem[]>(`/api/v1/approvals?status=${encodeURIComponent(status)}`);
}

// 提交人工审批结果。
export function decideApproval(payload: { approval_id: string; decision: "approved" | "rejected" | "needs_change"; reviewer_note?: string }) {
  return request<ApprovalDecisionResponse>(`/api/v1/approvals/${payload.approval_id}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision: payload.decision, reviewer_note: payload.reviewer_note ?? null })
  });
}

// 查询售后工单，Phase 3 售后面板使用。
export function fetchAfterSalesTickets(status = "open") {
  return request<AfterSalesTicket[]>(`/api/v1/after-sales?status=${encodeURIComponent(status)}`);
}

// 提交评价并获取 ReviewAgent 分析结果。
export function analyzeReview(payload: { user_id: string; order_id?: string | null; rating: number; content?: string | null }) {
  return request<ReviewAnalyzeResponse>("/api/v1/reviews/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// 查询运营报表，Phase 3 OpsAgent 使用。
export function fetchOpsReport() {
  return request<OpsReport>("/api/v1/ops/report");
}

// 查询知识库政策和服务说明。
export function queryKnowledge(payload: { query: string; category?: string | null }) {
  return request<KnowledgeAnswer>("/api/v1/knowledge/query", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// 解析用户位置：支持浏览器经纬度或文字地址。
export function resolveLocation(payload: LocationInput) {
  return request<any>("/api/v1/location/resolve", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// 推荐附近门店。
export function recommendStores(payload: LocationInput & { limit?: number }) {
  return request<StoreRecommendationResponse>("/api/v1/location/recommend-stores", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// ═══════════════════════════════════════════════════════════════════
// Admin API
// ═══════════════════════════════════════════════════════════════════

export function fetchDashboard() {
  return request<any>("/api/v1/admin/dashboard");
}
export function fetchAdminServices() { return request<any[]>("/api/v1/admin/services"); }
export function createService(payload: any) { return request<any>("/api/v1/admin/services", { method: "POST", body: JSON.stringify(payload) }); }
export function updateService(id: string, payload: any) { return request<any>(`/api/v1/admin/services/${id}`, { method: "PUT", body: JSON.stringify(payload) }); }
export function deleteService(id: string) { return request<any>(`/api/v1/admin/services/${id}`, { method: "DELETE" }); }

export function fetchAdminTechnicians() { return request<any[]>("/api/v1/admin/technicians"); }
export function createTechnician(payload: any) { return request<any>("/api/v1/admin/technicians", { method: "POST", body: JSON.stringify(payload) }); }
export function updateTechnician(id: string, payload: any) { return request<any>(`/api/v1/admin/technicians/${id}`, { method: "PUT", body: JSON.stringify(payload) }); }
export function deleteTechnician(id: string) { return request<any>(`/api/v1/admin/technicians/${id}`, { method: "DELETE" }); }

export function fetchAdminRooms() { return request<any[]>("/api/v1/admin/rooms"); }
export function createRoom(payload: any) { return request<any>("/api/v1/admin/rooms", { method: "POST", body: JSON.stringify(payload) }); }

export function fetchAdminSchedules() { return request<any[]>("/api/v1/admin/schedules"); }
export function createSchedule(payload: any) { return request<any>("/api/v1/admin/schedules", { method: "POST", body: JSON.stringify(payload) }); }

export function fetchAdminOrders(status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<any[]>(`/api/v1/admin/orders${q}`);
}
export function updateOrderStatus(id: string, status: string) {
  return request<any>(`/api/v1/admin/orders/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
}

export function fetchAdminReviews() { return request<any[]>("/api/v1/admin/reviews"); }
export function fetchAdminStore() { return request<any>("/api/v1/admin/store"); }
export function updateStore(payload: any) { return request<any>("/api/v1/admin/store", { method: "PUT", body: JSON.stringify(payload) }); }

// Knowledge collections
export function fetchKnowledgeCollections() { return request<any[]>("/api/v1/knowledge/collections"); }
export function fetchKnowledgeDocument(docId: string, collection?: string) {
  const q = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return request<any>(`/api/v1/knowledge/documents/${encodeURIComponent(docId)}${q}`);
}

export function uploadStoreManual(payload: { file: File; collection?: string; force?: boolean }) {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("collection", payload.collection ?? "massage_shop_rules");
  form.append("force", String(payload.force ?? false));
  return request<any>("/api/v1/knowledge/manuals/upload", {
    method: "POST",
    body: form
  });
}
