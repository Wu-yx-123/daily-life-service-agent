// 作用：预约候选卡片组件，展示服务、技师、时间、价格和确认按钮。
import { CalendarClock, Check, Clock, UserRound, MapPin } from "lucide-react";
import type { BookingOption } from "../../types/agent";

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
    .format(new Date(value));
}

export function BookingOptionCard({ option, confirming, onConfirm }: {
  option: BookingOption; confirming: boolean; onConfirm: (o: BookingOption) => void;
}) {
  return (
    <div style={{
      background: "#fff", borderRadius: 16, padding: "18px 20px",
      boxShadow: "0 2px 12px rgba(0,0,0,0.08)", border: "1px solid #e9ecef",
      maxWidth: 400,
    }}>
      {/* 顶部：服务名 + 价格 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1a1a2e" }}>{option.service_name}</h3>
        <span style={{ fontSize: 22, fontWeight: 700, color: "#e74c3c" }}>¥{option.final_price}</span>
      </div>

      {/* 技师 + 时间 */}
      <div style={{ display: "flex", gap: 20, marginBottom: 10, fontSize: 13, color: "#555" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <UserRound size={14} /> <span>{option.technician_name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <Clock size={14} />
          <span>{formatTime(option.appointment_start)} - {formatTime(option.appointment_end)}</span>
        </div>
      </div>

      {/* 推荐理由 */}
      <p style={{ margin: "0 0 14px", fontSize: 12, color: "#888", lineHeight: 1.5 }}>💡 {option.reason}</p>

      {/* 按钮 */}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={() => onConfirm(option)} disabled={confirming}
          style={{
            flex: 1, padding: "10px 0", border: "none", borderRadius: 10,
            background: confirming ? "#95a5a6" : "linear-gradient(135deg, #667eea, #764ba2)",
            color: "#fff", fontWeight: 600, fontSize: 14, cursor: confirming ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}>
          <Check size={16} /> {confirming ? "确认中..." : "确认预约"}
        </button>
        <button type="button" style={{
          padding: "10px 14px", border: "1px solid #e9ecef", borderRadius: 10,
          background: "#fff", color: "#888", cursor: "pointer", fontSize: 13,
          display: "flex", alignItems: "center", gap: 4,
        }}>
          <CalendarClock size={15} /> 稍后
        </button>
      </div>
    </div>
  );
}
