// 作用：实现 Phase 3 售后工单面板，展示取消、改期、退款和投诉工单。
import { RefreshCw, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchAfterSalesTickets } from "../../api/client";
import type { AfterSalesTicket } from "../../types/agent";

// 售后工单面板：先展示 open 工单，后续可扩展状态流转和订单关联。
export function AfterSalesPanel() {
  const [tickets, setTickets] = useState<AfterSalesTicket[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setTickets(await fetchAfterSalesTickets("open"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="after-sales-pane" aria-label="售后工单">
      <header className="approval-header">
        <div>
          <h2 className="trace-title">售后工单</h2>
          <p className="approval-subtitle">Phase 3 服务请求</p>
        </div>
        <button className="icon-button" onClick={load} disabled={loading} type="button" aria-label="刷新售后">
          <RefreshCw size={16} />
        </button>
      </header>
      <div className="approval-list">
        {tickets.length ? (
          tickets.map((ticket) => (
            <article className="approval-card" key={ticket.id}>
              <div className="approval-card-header">
                <Wrench size={18} />
                <strong>{ticket.ticket_type}</strong>
                <span>{ticket.priority}</span>
              </div>
              <p className="approval-message">{ticket.summary}</p>
              <p className="approval-reason">{ticket.suggested_action}</p>
              <div className="approval-meta">
                <span>{ticket.status}</span>
                <span>{new Date(ticket.created_at).toLocaleString("zh-CN")}</span>
              </div>
            </article>
          ))
        ) : (
          <p className="trace-empty">{loading ? "正在加载售后工单。" : "暂无开放售后工单。"}</p>
        )}
      </div>
    </section>
  );
}
