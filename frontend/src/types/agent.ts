// 作用：定义前端使用的 Agent、预约候选和订单确认 TypeScript 类型。
// 前后端共享的 Phase 1 API 类型，保持和 FastAPI Pydantic Schema 对齐。
export interface BookingOption {
  option_id: string;
  service_name: string;
  technician_name: string;
  appointment_start: string;
  appointment_end: string;
  final_price: string;
  reason: string;
}

export interface ConversationResponse {
  trace_id: string;
  session_id: string;
  response_type: "booking_options" | "followup" | "approval_required" | "service_ticket";
  message: string;
  options: BookingOption[];
}

export interface OrderConfirmResponse {
  order_id?: string | null;
  status: string;
  message: string;
}

export interface AgentStep {
  agent_name: string;
  step_name: string;
  status: string;
  latency_ms?: number;
  input?: unknown;
  output?: unknown;
  error_message?: string | null;
}

export interface AgentRunResponse {
  trace_id: string;
  steps: AgentStep[];
}

export interface ApprovalListItem {
  id: string;
  trace_id: string;
  session_id?: string | null;
  user_id: string;
  approval_type: string;
  status: string;
  risk_level: string;
  reason: string;
  snapshot: Record<string, unknown>;
  order_id?: string | null;
  reviewer_note?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface ApprovalDecisionResponse {
  id: string;
  status: string;
  message: string;
  order_id?: string | null;
}

export interface AfterSalesTicket {
  id: string;
  trace_id: string;
  session_id?: string | null;
  user_id: string;
  ticket_type: string;
  status: string;
  priority: string;
  summary: string;
  suggested_action: string;
  created_at: string;
  updated_at?: string | null;
}

export interface ReviewAnalyzeResponse {
  id: string;
  sentiment: string;
  reason_tags: string[];
  summary: string;
}

export interface OpsReport {
  order_count: number;
  revenue_total: string;
  after_sales_open_count: number;
  pending_approval_count: number;
  review_count: number;
  average_rating?: number | null;
  negative_review_count: number;
  suggestions: string[];
}

export interface KnowledgeDocumentHit {
  id: string;
  title: string;
  category: string;
  content: string;
}

export interface EvidenceChunk {
  source_file: string;
  doc_type: string;
  chunk_id: string;
  score: number;
  text: string;
}

export interface KnowledgeAnswer {
  query?: string;
  answer: string;
  evidence?: EvidenceChunk[];
  hits: KnowledgeDocumentHit[];
  source?: string;
}

export interface LocationInput {
  latitude?: number | null;
  longitude?: number | null;
  address?: string | null;
  city?: string | null;
}

export interface ResolvedLocation {
  latitude: number;
  longitude: number;
  formatted_address?: string | null;
  province?: string | null;
  city?: string | null;
  district?: string | null;
  source: string;
}

export interface StoreRecommendation {
  id: string;
  name: string;
  address: string;
  latitude?: number | null;
  longitude?: number | null;
  opening_time: string;
  closing_time: string;
  distance_km?: number | null;
  reason: string;
}

export interface StoreRecommendationResponse {
  location: ResolvedLocation;
  stores: StoreRecommendation[];
}
