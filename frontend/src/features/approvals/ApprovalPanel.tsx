// 作用：实现 Phase 2 人工审批面板，展示高风险 Agent 请求并提交审批结果。
import { Check, RefreshCw, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { decideApproval, fetchApprovals } from "../../api/client";
import type { ApprovalListItem } from "../../types/agent";

function snapshotText(item: ApprovalListItem) {
  const message = item.snapshot.user_message;
  return typeof message === "string" ? message : "无用户原文";
}

// 人工审批面板：Phase 2 先做可用后台入口，后续可拆成独立运营端页面。
export function ApprovalPanel() {
  const [items, setItems] = useState<ApprovalListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await fetchApprovals("pending"));
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(item: ApprovalListItem, decision: "approved" | "rejected") {
    setActingId(item.id);
    try {
      const result = await decideApproval({
        approval_id: item.id,
        decision,
        reviewer_note: decision === "approved" ? "人工复核通过" : "人工复核驳回"
      });
      setNotice(result.order_id ? `${result.message}：${result.order_id}` : result.message);
      await load();
    } finally {
      setActingId(null);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="approval-pane" aria-label="人工审批">
      <header className="approval-header">
        <div>
          <h2 className="trace-title">人工审批</h2>
          <p className="approval-subtitle">Phase 2 风险请求</p>
        </div>
        <button className="icon-button" onClick={load} disabled={loading} type="button" aria-label="刷新审批">
          <RefreshCw size={16} />
        </button>
      </header>
      {notice ? <p className="approval-notice">{notice}</p> : null}
      <div className="approval-list">
        {items.length ? (
          items.map((item) => (
            <article className="approval-card" key={item.id}>
              <div className="approval-card-header">
                <ShieldAlert size={18} />
                <strong>{item.risk_level.toUpperCase()}</strong>
                <span>{item.status}</span>
              </div>
              <p className="approval-message">{snapshotText(item)}</p>
              <p className="approval-reason">{item.reason}</p>
              <div className="approval-meta">
                <span>{item.trace_id}</span>
                <span>{new Date(item.created_at).toLocaleString("zh-CN")}</span>
              </div>
              <div className="confirm-row">
                <button className="primary-button" disabled={actingId === item.id} onClick={() => handleDecision(item, "approved")} type="button">
                  <Check size={16} />
                  通过
                </button>
                <button className="ghost-button" disabled={actingId === item.id} onClick={() => handleDecision(item, "rejected")} type="button">
                  <X size={16} />
                  驳回
                </button>
              </div>
            </article>
          ))
        ) : (
          <p className="trace-empty">{loading ? "正在加载审批单。" : "暂无待审批风险请求。"}</p>
        )}
      </div>
    </section>
  );
}
