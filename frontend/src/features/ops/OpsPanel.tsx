// 作用：实现 Phase 3 运营报表面板，展示 OpsAgent 指标和建议。
import { BarChart3, RefreshCw, SendHorizonal } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { analyzeReview, fetchOpsReport } from "../../api/client";
import type { OpsReport } from "../../types/agent";

const DEMO_USER_ID = "00000000-0000-0000-0000-000000000001";

// 运营面板：展示经营指标，并提供一个评价分析入口帮助生成 ReviewAgent 数据。
export function OpsPanel() {
  const [report, setReport] = useState<OpsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [reviewText, setReviewText] = useState("等太久了，手法也不舒服。");
  const [rating, setRating] = useState(2);
  const [reviewNotice, setReviewNotice] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setReport(await fetchOpsReport());
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(event: FormEvent) {
    event.preventDefault();
    const result = await analyzeReview({ user_id: DEMO_USER_ID, rating, content: reviewText });
    setReviewNotice(`${result.summary}${result.reason_tags.length ? `：${result.reason_tags.join("、")}` : ""}`);
    await load();
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="ops-pane" aria-label="运营报表">
      <header className="approval-header">
        <div>
          <h2 className="trace-title">运营报表</h2>
          <p className="approval-subtitle">Phase 3 OpsAgent</p>
        </div>
        <button className="icon-button" onClick={load} disabled={loading} type="button" aria-label="刷新运营报表">
          <RefreshCw size={16} />
        </button>
      </header>
      {report ? (
        <>
          <div className="ops-metrics">
            <div><strong>{report.order_count}</strong><span>订单</span></div>
            <div><strong>¥{report.revenue_total}</strong><span>营收</span></div>
            <div><strong>{report.after_sales_open_count}</strong><span>售后</span></div>
            <div><strong>{report.pending_approval_count}</strong><span>审批</span></div>
          </div>
          <div className="approval-card">
            <div className="approval-card-header">
              <BarChart3 size={18} />
              <strong>评分 {report.average_rating?.toFixed(1) ?? "-"}</strong>
              <span>{report.negative_review_count} 差评</span>
            </div>
            {report.suggestions.map((item) => (
              <p className="approval-message" key={item}>{item}</p>
            ))}
          </div>
        </>
      ) : (
        <p className="trace-empty">{loading ? "正在生成运营报表。" : "暂无运营报表。"}</p>
      )}
      <form className="ops-review-form" onSubmit={handleReview}>
        <label>
          <span>评分</span>
          <input min={1} max={5} type="number" value={rating} onChange={(event) => setRating(Number(event.target.value))} />
        </label>
        <label>
          <span>评价</span>
          <input value={reviewText} onChange={(event) => setReviewText(event.target.value)} />
        </label>
        <button className="primary-button" type="submit">
          <SendHorizonal size={16} />
          分析评价
        </button>
      </form>
      {reviewNotice ? <p className="approval-notice">{reviewNotice}</p> : null}
    </section>
  );
}
