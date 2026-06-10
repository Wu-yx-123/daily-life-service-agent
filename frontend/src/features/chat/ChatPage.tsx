// 作用：用户端聊天预约页面，支持自然语言输入、位置推荐、候选方案展示、确认预约和 Trace。
import { Bot, LocateFixed, MapPin, Navigation, SendHorizonal, Sparkles, User } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { confirmOrder, fetchAgentRun, recommendStores, sendMessage } from "../../api/client";
import { AgentTimeline } from "../agent-runs/AgentTimeline";
import type { AgentStep, BookingOption, StoreRecommendation } from "../../types/agent";
import { BookingOptionCard } from "./BookingOptionCard";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  traceId?: string;
  options?: BookingOption[];
  stores?: StoreRecommendation[];
}

const QUICK_ACTIONS = [
  "今晚8点想约个肩颈按摩，力度重一点",
  "帮我推荐一个全身放松的技师",
  "我想取消之前的预约",
];

export function ChatPage({ userId, userName, onLogout }: { userId: string; userName?: string; onLogout?: () => void }) {
  const DEMO_USER_ID = userId;
  const sessionId = useMemo(() => `session_${Math.random().toString(16).slice(2)}`, []);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "agent",
      text: `你好${userName ? ` ${userName}` : ""}！👋 我是智能预约助手，可以帮你：\n• 预约按摩/SPA/理疗服务\n• 匹配最适合的技师和时间\n• 处理取消、改期、退款等售后\n\n你可以直接告诉我需求，比如：`,
    }
  ]);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [locating, setLocating] = useState(false);
  const [confirmingOptionId, setConfirmingOptionId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [streamSteps, setStreamSteps] = useState<{ step: string; agent: string; message: string; status: string }[]>([]);

  async function refreshTrace(nextTraceId: string) {
    try { const trace = await fetchAgentRun(nextTraceId); setSteps(trace.steps); } catch {}
  }

  async function handleSubmit(event?: FormEvent, text?: string) {
    event?.preventDefault();
    const content = (text || input).trim();
    if (!content || loading) return;
    setLoading(true); setError(""); setStreamSteps([]);
    if (!text) setInput("");
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "user", text: content }]);

    // SSE 流式请求
    try {
      const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "";
      const savedUser = sessionStorage.getItem("massageops_user");
      const token = savedUser ? JSON.parse(savedUser)?.access_token : null;
      const resp = await fetch(`${API_BASE}/api/v1/conversations/message/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId, user_id: DEMO_USER_ID, message: content }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No stream reader");
      const decoder = new TextDecoder();
      let buffer = "";
      let finalData: any = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6);
          if (jsonStr === "[DONE]") continue;
          try {
            const evt = JSON.parse(jsonStr);
            if (evt.type === "trace_created") setTraceId(evt.trace_id);
            else if (evt.type === "step_started")
              setStreamSteps(prev => [...prev, { ...evt, status: "running" }]);
            else if (evt.type === "step_finished")
              setStreamSteps(prev => prev.map(s => s.step === evt.step ? { ...s, status: evt.status } : s));
            else if (evt.type === "final") finalData = evt.data;
          } catch {}
        }
      }

      if (finalData) {
        setMessages(prev => [...prev, { id: finalData.trace_id || crypto.randomUUID(), role: "agent",
          text: finalData.message, traceId: finalData.trace_id, options: finalData.options }]);
        if (finalData.trace_id) await refreshTrace(finalData.trace_id);
      } else {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "agent", text: "请求完成但无返回数据" }]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "请求失败，请稍后重试";
      setError(msg);
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "agent", text: `❌ ${msg}` }]);
    } finally {
      setLoading(false);
      setStreamSteps([]);
    }
  }

  async function handleConfirm(option: BookingOption, optionTraceId?: string) {
    const confirmTraceId = optionTraceId || traceId;
    if (!confirmTraceId) return;
    setConfirmingOptionId(option.option_id);
    try {
      const response = await confirmOrder({ trace_id: confirmTraceId, option_id: option.option_id, user_confirmed: true });
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: "agent",
        text: response.order_id ? `✅ ${response.message}\n\n订单号：\`${response.order_id}\`` : response.message
      }]);
      await refreshTrace(confirmTraceId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "确认失败";
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "agent", text: `❌ ${msg}` }]);
    } finally {
      setConfirmingOptionId(null);
    }
  }

  async function handleLocateAndRecommend() {
    if (locating || loading) return;
    if (!navigator.geolocation) {
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "agent", text: "当前浏览器不支持定位，可以直接输入你所在的城市或商圈，我来帮你推荐门店。" }]);
      return;
    }
    setLocating(true);
    setError("");
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "user", text: "帮我定位并推荐附近门店" }]);
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000,
        });
      });
      const result = await recommendStores({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        limit: 5,
      });
      const address = result.location.formatted_address || `${result.location.latitude.toFixed(5)}, ${result.location.longitude.toFixed(5)}`;
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: "agent",
        text: `已根据你的位置推荐附近门店。\n当前位置：${address}`,
        stores: result.stores,
      }]);
    } catch (err) {
      const detail = err instanceof GeolocationPositionError
        ? "定位授权失败或超时，请允许浏览器定位后重试。"
        : err instanceof Error ? err.message : "定位失败，请稍后重试。";
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "agent", text: `❌ ${detail}\n你也可以直接输入“我在上海人民广场附近”，我来按地址推荐。` }]);
    } finally {
      setLocating(false);
    }
  }

  return (
    <div style={{ display: "flex", height: "100vh", background: "#f8f9fa" }}>
      {/* 左侧聊天 */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", maxWidth: 720, margin: "0 auto", width: "100%" }}>
        {/* 顶栏 */}
        <header style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 24px", background: "#fff", borderBottom: "1px solid #e9ecef",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "linear-gradient(135deg, #667eea, #764ba2)",
              display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Sparkles size={18} color="#fff" />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>MassageOps</div>
              <div style={{ fontSize: 11, color: "#888" }}>智能预约助手</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{
              padding: "4px 10px", borderRadius: 12, fontSize: 12, fontWeight: 500,
              background: loading ? "#fff3cd" : "#d4edda", color: loading ? "#856404" : "#155724",
            }}>
              <Bot size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />
              {loading ? "思考中..." : "在线"}
            </span>
            {onLogout && (
              <button type="button" onClick={onLogout} style={{
                background: "none", border: "1px solid #ddd", borderRadius: 6, padding: "4px 10px",
                cursor: "pointer", fontSize: 12, color: "#666",
              }}>退出</button>
            )}
          </div>
        </header>

        {/* 消息区 */}
        <div style={{ flex: 1, overflow: "auto", padding: "20px 24px" }}>
          {messages.map(msg => (
            <div key={msg.id} style={{ marginBottom: 20 }}>
              {/* 消息气泡 */}
              <div style={{
                display: "flex", gap: 10, alignItems: "flex-start",
                flexDirection: msg.role === "user" ? "row-reverse" : "row",
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: msg.role === "user" ? "#667eea" : "#e9ecef",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0,
                }}>
                  {msg.role === "user" ? <User size={16} color="#fff" /> : <Bot size={16} color="#666" />}
                </div>
                <div style={{
                  maxWidth: "80%", padding: "12px 16px", borderRadius: 16,
                  background: msg.role === "user" ? "#667eea" : "#fff",
                  color: msg.role === "user" ? "#fff" : "#333",
                  borderTopLeftRadius: msg.role === "agent" ? 4 : 16,
                  borderTopRightRadius: msg.role === "user" ? 4 : 16,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
                  fontSize: 14, lineHeight: 1.7, whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {msg.text}
                </div>
              </div>

              {/* 预约候选卡片 */}
              {msg.options && msg.options.length > 0 && (
                <div style={{ marginLeft: 42, marginTop: 10, display: "flex", flexDirection: "column", gap: 10 }}>
                  {msg.options.map(option => (
                    <BookingOptionCard
                      key={option.option_id}
                      option={option}
                      confirming={confirmingOptionId === option.option_id}
                      onConfirm={() => handleConfirm(option, msg.traceId)}
                    />
                  ))}
                </div>
              )}

              {/* 附近门店推荐卡片 */}
              {msg.stores && msg.stores.length > 0 && (
                <div style={{ marginLeft: 42, marginTop: 10, display: "flex", flexDirection: "column", gap: 10 }}>
                  {msg.stores.map(store => <StoreRecommendationCard key={store.id} store={store} />)}
                </div>
              )}
            </div>
          ))}

          {/* 快捷操作 */}
          {messages.length <= 1 && !loading && (
            <div style={{ marginLeft: 42, marginTop: 8 }}>
              <div style={{ fontSize: 12, color: "#aaa", marginBottom: 8 }}>试试这些：</div>
              {QUICK_ACTIONS.map((action, i) => (
                <button key={i} type="button" onClick={() => handleSubmit(undefined, action)}
                  style={{
                    display: "block", padding: "8px 14px", marginBottom: 6, fontSize: 13,
                    background: "#fff", border: "1px solid #e9ecef", borderRadius: 20,
                    cursor: "pointer", color: "#667eea", textAlign: "left",
                  }}>
                  💬 {action}
                </button>
              ))}
              <button type="button" onClick={handleLocateAndRecommend}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 7, padding: "8px 14px", marginTop: 4,
                  fontSize: 13, background: "linear-gradient(135deg, #eef8f1, #e8f1ff)",
                  border: "1px solid #cfe3d4", borderRadius: 20, cursor: "pointer", color: "#2f6650",
                }}>
                <LocateFixed size={14} /> 定位并推荐附近门店
              </button>
            </div>
          )}

          {/* SSE 流式进度条 */}
          {loading && (
            <div style={{ marginLeft: 42, marginTop: 10, background: "#fff", borderRadius: 12, padding: "12px 16px",
                          boxShadow: "0 1px 4px rgba(0,0,0,0.08)", maxWidth: 360 }}>
              {streamSteps.length > 0 ? (
                streamSteps.map((s, i) => (
                  <div key={s.step} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 13 }}>
                    <span style={{ width: 18, textAlign: "center" }}>
                      {s.status === "success" ? "✅" : s.status === "error" ? "❌" : "⏳"}
                    </span>
                    <span style={{ color: s.status === "running" ? "#333" : s.status === "error" ? "#e74c3c" : "#999" }}>
                      {s.agent}
                    </span>
                    <span style={{ color: "#aaa", fontSize: 11 }}>{s.message}</span>
                  </div>
                ))
              ) : (
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <Bot size={16} color="#aaa" />
                  <span style={{ fontSize: 13, color: "#aaa" }}>Agent 初始化中…</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 错误提示 */}
        {error && (
          <div style={{
            margin: "0 24px", padding: "8px 14px", background: "#fee", color: "#c0392b",
            borderRadius: 8, fontSize: 13,
          }}>
            {error}
            <button type="button" onClick={() => setError("")} style={{ float: "right", background: "none", border: "none", cursor: "pointer", color: "#c0392b" }}>✕</button>
          </div>
        )}

        {/* 输入区 */}
        <form onSubmit={handleSubmit} style={{
          padding: "14px 24px", background: "#fff", borderTop: "1px solid #e9ecef",
        }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={handleLocateAndRecommend}
              aria-label="定位推荐门店"
              title="定位并推荐附近门店"
              disabled={loading || locating}
              style={{
                width: 48, height: 48, borderRadius: 12, border: "1px solid #d6eadf",
                background: locating ? "#e9f5ef" : "#f3fbf6",
                color: "#2f6650", cursor: loading || locating ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              {locating ? <Navigation size={18} /> : <LocateFixed size={18} />}
            </button>
            <input
              value={input} onChange={e => setInput(e.target.value)}
              placeholder="描述你的需求，如「今晚8点肩颈按摩，力度重一点」"
              disabled={loading}
              style={{
                flex: 1, padding: "12px 16px", border: "2px solid #e9ecef", borderRadius: 12,
                fontSize: 14, outline: "none", background: loading ? "#f5f5f5" : "#fff",
              }}
            />
            <button
              type="submit"
              aria-label="发送"
              title={!input.trim() ? "请输入预约需求后发送" : "发送"}
              disabled={loading || !input.trim()}
              style={{
                width: 48, height: 48, borderRadius: 12, border: "none",
                background: loading || !input.trim() ? "#ccc" : "#667eea",
                color: "#fff", cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <SendHorizonal size={18} />
            </button>
          </div>
        </form>
      </div>

      {/* 右侧 Trace */}
      <aside style={{
        width: 300, background: "#fff", borderLeft: "1px solid #e9ecef",
        overflow: "auto", padding: "16px", display: "flex", flexDirection: "column",
      }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#333" }}>🔍 Agent 执行轨迹</h3>
        {steps.length > 0 ? (
          <AgentTimeline steps={steps} />
        ) : (
          <div style={{ color: "#ccc", fontSize: 13, textAlign: "center", marginTop: 40 }}>
            发送预约需求后<br/>这里会展示 Agent 执行过程
          </div>
        )}
      </aside>
    </div>
  );
}

function StoreRecommendationCard({ store }: { store: StoreRecommendation }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 16, padding: "16px 18px",
      boxShadow: "0 2px 12px rgba(0,0,0,0.08)", border: "1px solid #e9ecef",
      maxWidth: 420,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h3 style={{ margin: "0 0 6px", fontSize: 16, fontWeight: 700, color: "#1a1a2e" }}>{store.name}</h3>
          <div style={{ display: "flex", gap: 6, alignItems: "flex-start", color: "#666", fontSize: 13, lineHeight: 1.5 }}>
            <MapPin size={14} style={{ marginTop: 2, flexShrink: 0 }} />
            <span>{store.address}</span>
          </div>
        </div>
        {store.distance_km != null && (
          <span style={{
            padding: "5px 9px", borderRadius: 999, background: "#eef8f1",
            color: "#2f6650", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap",
          }}>
            {store.distance_km.toFixed(1)} km
          </span>
        )}
      </div>
      <p style={{ margin: "10px 0 0", color: "#888", fontSize: 12, lineHeight: 1.5 }}>💡 {store.reason}</p>
    </div>
  );
}
