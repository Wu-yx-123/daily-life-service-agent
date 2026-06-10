import React, { useEffect, useState } from "react";
import {
  fetchDashboard, fetchAdminServices, fetchAdminTechnicians,
  fetchAdminSchedules, fetchAdminOrders, fetchAdminReviews, fetchAdminStore,
  updateOrderStatus,
  createService, createTechnician, createSchedule, updateStore, uploadStoreManual,
  updateService, deleteService, updateTechnician, deleteTechnician,
} from "../../api/client";
import { fetchApprovals, decideApproval } from "../../api/client";
import { KnowledgePanel } from "../knowledge/KnowledgePanel";

type Tab = "dashboard" | "approvals" | "orders" | "services" | "technicians" | "schedules" | "reviews" | "store" | "knowledge";
const TABS: { key: Tab; label: string }[] = [
  { key: "dashboard", label: "📊 面板" }, { key: "approvals", label: "🛡 审批" },
  { key: "orders", label: "📋 订单" }, { key: "services", label: "💆 服务" },
  { key: "technicians", label: "👨‍⚕ 技师" }, { key: "schedules", label: "📅 排班" },
  { key: "reviews", label: "⭐ 评价" }, { key: "store", label: "🏪 门店" },
  { key: "knowledge", label: "📚 知识库" },
];

const SERVICE_PRESETS = [
  { name: "肩颈舒缓 60 分钟", category: "肩颈理疗", duration_minutes: 60, base_price: 198, description: "适合久坐、低头族和肩颈紧张用户，重点放松颈肩、斜方肌和上背。", tags: ["肩颈", "久坐", "放松"] },
  { name: "深层经络 90 分钟", category: "中式推拿", duration_minutes: 90, base_price: 328, description: "以经络推拿和深层按压为主，适合长期疲劳、肌肉僵硬和喜欢偏重力度的用户。", tags: ["经络", "力度偏重", "疲劳恢复"] },
  { name: "全身放松 90 分钟", category: "全身按摩", duration_minutes: 90, base_price: 298, description: "覆盖肩背、腰腿和头部放松，节奏舒缓，适合下班后恢复和改善睡眠。", tags: ["全身", "放松", "助眠"] },
  { name: "足底反射 60 分钟", category: "足疗", duration_minutes: 60, base_price: 168, description: "围绕足底反射区、腿部循环和小腿放松，适合久站、走路多和腿部疲劳用户。", tags: ["足底", "反射区", "循环"] },
  { name: "运动拉伸 75 分钟", category: "运动康复", duration_minutes: 75, base_price: 268, description: "结合筋膜放松、关节活动和被动拉伸，适合健身后、跑步后和办公室僵硬人群。", tags: ["拉伸", "筋膜", "运动恢复"] },
  { name: "精油 SPA 60 分钟", category: "芳香 SPA", duration_minutes: 60, base_price: 268, description: "轻量芳香舒压护理，适合午休、下班后快速放松。", tags: ["精油", "舒压", "轻柔"] },
  { name: "精油 SPA 90 分钟", category: "芳香 SPA", duration_minutes: 90, base_price: 358, description: "覆盖背部、腿部和肩颈的完整芳香护理，适合压力大、睡眠浅的用户。", tags: ["精油", "舒压", "轻柔"] },
  { name: "精油 SPA 100 分钟", category: "芳香 SPA", duration_minutes: 100, base_price: 398, description: "使用基础精油进行轻柔舒压护理，偏放松体验，适合深度放松。", tags: ["精油", "舒压", "轻柔"] },
];

const TECHNICIAN_PRESETS = [
  { name: "李师傅", skill_tags: ["肩颈理疗", "力度偏重", "深层经络"], rating: 4.8 },
  { name: "王老师", skill_tags: ["全身放松", "助眠舒压", "力度适中"], rating: 4.7 },
  { name: "陈师傅", skill_tags: ["运动拉伸", "筋膜放松", "康复护理"], rating: 4.9 },
  { name: "赵老师", skill_tags: ["足底反射", "腿部放松", "循环改善"], rating: 4.6 },
  { name: "刘师傅", skill_tags: ["中式推拿", "腰背调理", "疲劳恢复"], rating: 4.8 },
  { name: "周老师", skill_tags: ["精油 SPA", "轻柔舒压", "女性护理"], rating: 4.9 },
];

export function AdminPanel({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("dashboard");
  return (
    <div style={{ display: "flex", height: "100vh", background: "#f5f5f5" }}>
      <nav style={{ width: 160, background: "#1a1a2e", color: "#eee", padding: "20px 0", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "0 16px 16px", fontWeight: 700, fontSize: 16, borderBottom: "1px solid #333" }}>MassageOps</div>
        {TABS.map(t => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            style={{ background: tab === t.key ? "#16213e" : "transparent", color: "#eee", border: "none",
              padding: "12px 16px", textAlign: "left", cursor: "pointer", fontSize: 14 }}>
            {t.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button type="button" onClick={onLogout} style={{ background: "transparent", color: "#999", border: "none", padding: "12px 16px", cursor: "pointer" }}>🚪 退出</button>
      </nav>
      <main style={{ flex: 1, overflow: "auto", padding: 24 }}>
        {tab === "dashboard" && <DashboardTab />}
        {tab === "approvals" && <ApprovalsTab />}
        {tab === "orders" && <OrdersTab />}
        {tab === "services" && <ServicesTab />}
        {tab === "technicians" && <TechniciansTab />}
        {tab === "schedules" && <SchedulesTab />}
        {tab === "reviews" && <ReviewsTab />}
        {tab === "store" && <StoreTab />}
        {tab === "knowledge" && <KnowledgeAdminTab />}
      </main>
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────

function DashboardTab() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetchDashboard().then(setData).catch(console.error); }, []);
  if (!data) return <div>加载中...</div>;
  return (
    <div>
      <h2>运营面板</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginTop: 16 }}>
        <MetricCard label="今日订单" value={data.orders_today} />
        <MetricCard label="今日营收" value={`¥${data.revenue_today.toFixed(2)}`} />
        <MetricCard label="总订单" value={data.total_orders} />
        <MetricCard label="总营收" value={`¥${data.total_revenue.toFixed(2)}`} />
        <MetricCard label="活跃服务" value={data.active_services} />
        <MetricCard label="活跃技师" value={data.active_technicians} />
        <MetricCard label="售后待处理" value={data.open_after_sales} color={data.open_after_sales > 0 ? "#e74c3c" : undefined} />
        <MetricCard label="待审批" value={data.pending_approvals} color={data.pending_approvals > 0 ? "#f39c12" : undefined} />
      </div>
      {data.average_rating !== null && <p style={{ marginTop: 16 }}>平均评分：⭐ {data.average_rating.toFixed(1)}</p>}
      <h3 style={{ marginTop: 20 }}>最近订单</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ background: "#eee" }}>{["订单ID","状态","金额","预约时间","创建时间"].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>{data.recent_orders?.map((o: any) => (
          <tr key={o.id} style={{ borderBottom: "1px solid #ddd" }}>
            <td style={tdStyle}>{o.id?.slice(0,12)}</td><td style={tdStyle}>{o.status}</td>
            <td style={tdStyle}>¥{o.final_price}</td><td style={tdStyle}>{o.appointment_start?.slice(0,16)}</td>
            <td style={tdStyle}>{o.created_at?.slice(0,16)}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
function MetricCard({ label, value, color }: { label: string; value: any; color?: string }) {
  return <div style={{ background: "#fff", padding: 16, borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,0.1)" }}>
    <div style={{ fontSize: 13, color: "#888" }}>{label}</div>
    <div style={{ fontSize: 24, fontWeight: 700, color: color || "#333", marginTop: 4 }}>{value}</div>
  </div>;
}

// ── Approvals ──────────────────────────────────────────────────────────

function ApprovalsTab() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => { setLoading(true); fetchApprovals("pending").then(d => { setItems(d); setLoading(false); }).catch(() => setLoading(false)); };
  useEffect(load, []);
  const handle = async (id: string, decision: "approved" | "rejected") => {
    await decideApproval({ approval_id: id, decision });
    load();
  };
  return (
    <div>
      <h2>审批中心</h2>
      {loading && <p>加载中...</p>}
      {!loading && !items.length && <p>暂无待审批请求 ✅</p>}
      {items.map(item => (
        <div key={item.id} style={{ background: "#fff", padding: 16, margin: "12px 0", borderRadius: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong>{item.approval_type}</strong>
            <span style={{ color: item.risk_level === "high" ? "#e74c3c" : "#f39c12" }}>⚠ {item.risk_level}</span>
          </div>
          <p style={{ color: "#666", margin: "8px 0" }}>{item.reason}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={() => handle(item.id, "approved")} style={btnGreen}>✅ 批准</button>
            <button type="button" onClick={() => handle(item.id, "rejected")} style={btnRed}>❌ 驳回</button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Orders ─────────────────────────────────────────────────────────────

function OrdersTab() {
  const [orders, setOrders] = useState<any[]>([]);
  const [filter, setFilter] = useState("");
  useEffect(() => { fetchAdminOrders(filter || undefined).then(setOrders).catch(console.error); }, [filter]);
  const changeStatus = async (id: string, status: string) => {
    await updateOrderStatus(id, status);
    setOrders(prev => prev.map(o => o.id === id ? { ...o, status } : o));
  };
  return (
    <div>
      <h2>订单管理</h2>
      <select value={filter} onChange={e => setFilter(e.target.value)} style={{ padding: 6, marginBottom: 12 }}>
        <option value="">全部</option><option value="confirmed">已确认</option><option value="cancelled">已取消</option><option value="completed">已完成</option><option value="refunded">已退款</option>
      </select>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ background: "#eee" }}>{["ID","状态","金额","预约时间","操作"].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>{orders.map(o => (
          <tr key={o.id} style={{ borderBottom: "1px solid #ddd" }}>
            <td style={tdStyle}>{o.id?.slice(0,12)}</td><td style={tdStyle}>{o.status}</td>
            <td style={tdStyle}>¥{o.final_price}</td><td style={tdStyle}>{o.appointment_start?.slice(0,16)}</td>
            <td style={tdStyle}>
              <select value={o.status} onChange={e => changeStatus(o.id, e.target.value)} style={{ padding: 4 }}>
                <option value="confirmed">已确认</option><option value="completed">已完成</option><option value="cancelled">已取消</option><option value="refunded">已退款</option>
              </select>
            </td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

// ── Services CRUD ──────────────────────────────────────────────────────

function ServicesTab() {
  const [items, setItems] = useState<any[]>([]);
  const load = () => fetchAdminServices().then(setItems);
  useEffect(() => { load(); }, []);
  const [form, setForm] = useState({ name: "", duration_minutes: 60, base_price: 198, category: "", description: "" });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", duration_minutes: 60, base_price: 198, category: "", description: "" });
  const [error, setError] = useState("");
  const submit = async () => { await createService(form); load(); setForm({ name: "", duration_minutes: 60, base_price: 198, category: "", description: "" }); };
  const importPresets = async () => {
    setError("");
    const existingNames = new Set(items.map(item => item.name));
    const missing = SERVICE_PRESETS.filter(item => !existingNames.has(item.name));
    if (!missing.length) { setError("常用示例服务已经存在，无需重复添加。"); return; }
    await Promise.all(missing.map(item => createService(item)));
    await load();
  };
  const startEdit = (item: any) => {
    setEditingId(item.id);
    setEditForm({
      name: item.name || "",
      duration_minutes: item.duration_minutes || 60,
      base_price: item.base_price || 198,
      category: item.category || "",
      description: item.description || "",
    });
  };
  const saveEdit = async (item: any) => {
    await updateService(item.id, { ...editForm, tags: item.tags || [] });
    setEditingId(null);
    await load();
  };
  const remove = async (item: any) => {
    if (!window.confirm(`确定删除服务「${item.name}」吗？`)) return;
    await deleteService(item.id);
    await load();
  };
  return (
    <div>
      <h2>服务项目管理</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <input placeholder="名称" value={form.name} onChange={e => setForm({...form, name: e.target.value})} style={inputStyle} />
        <input placeholder="分类" value={form.category} onChange={e => setForm({...form, category: e.target.value})} style={{...inputStyle, width:100}} />
        <input type="number" placeholder="时长(分)" value={form.duration_minutes} onChange={e => setForm({...form, duration_minutes: +e.target.value})} style={{...inputStyle, width:80}} />
        <input type="number" placeholder="价格" value={form.base_price} onChange={e => setForm({...form, base_price: +e.target.value})} style={{...inputStyle, width:100}} />
        <button type="button" onClick={submit} style={btnGreen}>➕ 添加</button>
        <button type="button" onClick={importPresets} style={btnBlue}>✨ 一键添加常用真实服务</button>
      </div>
      {error && <p style={{ color: "#e67e22", marginTop: 0 }}>{error}</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ background: "#eee" }}>{["名称","分类","时长","价格","状态","操作"].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>{items.map(s => (
          <tr key={s.id} style={{ borderBottom: "1px solid #ddd" }}>
            {editingId === s.id ? (
              <>
                <td style={tdStyle}><input value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})} style={inputStyle} /></td>
                <td style={tdStyle}><input value={editForm.category} onChange={e => setEditForm({...editForm, category: e.target.value})} style={{...inputStyle, width:100}} /></td>
                <td style={tdStyle}><input type="number" value={editForm.duration_minutes} onChange={e => setEditForm({...editForm, duration_minutes: +e.target.value})} style={{...inputStyle, width:80}} /></td>
                <td style={tdStyle}><input type="number" value={editForm.base_price} onChange={e => setEditForm({...editForm, base_price: +e.target.value})} style={{...inputStyle, width:90}} /></td>
                <td style={tdStyle}>{s.status}</td>
                <td style={tdStyle}>
                  <button type="button" onClick={() => saveEdit(s)} style={btnGreen}>保存</button>
                  <button type="button" onClick={() => setEditingId(null)} style={btnGray}>取消</button>
                </td>
              </>
            ) : (
              <>
                <td style={tdStyle}>{s.name}</td><td style={tdStyle}>{s.category}</td><td style={tdStyle}>{s.duration_minutes}分</td>
                <td style={tdStyle}>¥{s.base_price}</td><td style={tdStyle}>{s.status}</td>
                <td style={tdStyle}>
                  <button type="button" onClick={() => startEdit(s)} style={btnBlue}>编辑</button>
                  <button type="button" onClick={() => remove(s)} style={btnRed}>删除</button>
                </td>
              </>
            )}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

// ── Technicians ────────────────────────────────────────────────────────

function TechniciansTab() {
  const [items, setItems] = useState<any[]>([]);
  const load = () => fetchAdminTechnicians().then(setItems);
  useEffect(() => { load(); }, []);
  const [form, setForm] = useState({ name: "", skill_tags: "", rating: 4.5 });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", skill_tags: "", rating: 4.5 });
  const [error, setError] = useState("");
  const toTags = (value: string) => value.split(/[,，]/).map(tag => tag.trim()).filter(Boolean);
  const submit = async () => {
    await createTechnician({ name: form.name, skill_tags: toTags(form.skill_tags), rating: form.rating });
    setForm({ name: "", skill_tags: "", rating: 4.5 });
    load();
  };
  const importPresets = async () => {
    setError("");
    const existingNames = new Set(items.map(item => item.name));
    const missing = TECHNICIAN_PRESETS.filter(item => !existingNames.has(item.name));
    if (!missing.length) { setError("6 位示例技师已经存在，无需重复添加。"); return; }
    await Promise.all(missing.map(item => createTechnician(item)));
    await load();
  };
  const startEdit = (item: any) => {
    setEditingId(item.id);
    setEditForm({
      name: item.name || "",
      skill_tags: (item.skill_tags || []).join("，"),
      rating: item.rating || 4.5,
    });
  };
  const saveEdit = async (item: any) => {
    await updateTechnician(item.id, { name: editForm.name, skill_tags: toTags(editForm.skill_tags), rating: editForm.rating });
    setEditingId(null);
    await load();
  };
  const remove = async (item: any) => {
    if (!window.confirm(`确定删除技师「${item.name}」吗？`)) return;
    await deleteTechnician(item.id);
    await load();
  };
  return (
    <div>
      <h2>技师管理</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <input placeholder="技师姓名" value={form.name} onChange={e => setForm({...form, name: e.target.value})} style={inputStyle} />
        <input placeholder="技能标签，用逗号分隔" value={form.skill_tags} onChange={e => setForm({...form, skill_tags: e.target.value})} style={{...inputStyle, width:220}} />
        <input type="number" step="0.1" min="0" max="5" placeholder="评分" value={form.rating} onChange={e => setForm({...form, rating: +e.target.value})} style={{...inputStyle, width:80}} />
        <button type="button" onClick={submit} style={btnGreen}>➕ 添加</button>
        <button type="button" onClick={importPresets} style={btnBlue}>✨ 一键添加 6 位真实技师</button>
      </div>
      {error && <p style={{ color: "#e67e22", marginTop: 0 }}>{error}</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ background: "#eee" }}>{["姓名","技能标签","评分","状态","操作"].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>{items.map(t => (
          <tr key={t.id} style={{ borderBottom: "1px solid #ddd" }}>
            {editingId === t.id ? (
              <>
                <td style={tdStyle}><input value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})} style={inputStyle} /></td>
                <td style={tdStyle}><input value={editForm.skill_tags} onChange={e => setEditForm({...editForm, skill_tags: e.target.value})} style={{...inputStyle, width:220}} /></td>
                <td style={tdStyle}><input type="number" step="0.1" min="0" max="5" value={editForm.rating} onChange={e => setEditForm({...editForm, rating: +e.target.value})} style={{...inputStyle, width:80}} /></td>
                <td style={tdStyle}>{t.status}</td>
                <td style={tdStyle}>
                  <button type="button" onClick={() => saveEdit(t)} style={btnGreen}>保存</button>
                  <button type="button" onClick={() => setEditingId(null)} style={btnGray}>取消</button>
                </td>
              </>
            ) : (
              <>
                <td style={tdStyle}>{t.name}</td><td style={tdStyle}>{(t.skill_tags||[]).join(",")}</td>
                <td style={tdStyle}>{t.rating}</td><td style={tdStyle}>{t.status}</td>
                <td style={tdStyle}>
                  <button type="button" onClick={() => startEdit(t)} style={btnBlue}>编辑</button>
                  <button type="button" onClick={() => remove(t)} style={btnRed}>删除</button>
                </td>
              </>
            )}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

// ── Schedules + Rooms + Reviews + Store (精简版) ───────────────────────

function SchedulesTab() {
  const [items, setItems] = useState<any[]>([]);
  const [techs, setTechs] = useState<any[]>([]);
  const load = () => { fetchAdminSchedules().then(setItems); fetchAdminTechnicians().then(setTechs); };
  useEffect(() => { load(); }, []);
  const [form, setForm] = useState({ technician_id: "", work_date: "", start_time: "", end_time: "" });
  const submit = async () => { await createSchedule(form); load(); };
  return (
    <div>
      <h2>排班管理</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <select value={form.technician_id} onChange={e => setForm({...form, technician_id: e.target.value})} style={inputStyle}>
          <option value="">选择技师</option>
          {techs.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <input type="date" value={form.work_date} onChange={e => setForm({...form, work_date: e.target.value})} style={inputStyle} />
        <input type="datetime-local" value={form.start_time} onChange={e => setForm({...form, start_time: e.target.value})} style={inputStyle} />
        <input type="datetime-local" value={form.end_time} onChange={e => setForm({...form, end_time: e.target.value})} style={inputStyle} />
        <button type="button" onClick={submit} style={btnGreen}>➕ 添加</button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ background: "#eee" }}>{["日期","开始","结束","技师","状态"].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>{items.map(s => {
          const t = techs.find(x => x.id === s.technician_id);
          return <tr key={s.id} style={{ borderBottom: "1px solid #ddd" }}>
            <td style={tdStyle}>{s.work_date}</td><td style={tdStyle}>{s.start_time?.slice(0,16)}</td>
            <td style={tdStyle}>{s.end_time?.slice(0,16)}</td><td style={tdStyle}>{t?.name || s.technician_id?.slice(0,8)}</td>
            <td style={tdStyle}>{s.status}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}

function ReviewsTab() {
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => { fetchAdminReviews().then(setItems); }, []);
  return (
    <div>
      <h2>评价管理</h2>
      {items.map(r => (
        <div key={r.id} style={{ background: "#fff", padding: 12, margin: "8px 0", borderRadius: 6 }}>
          <span>{"⭐".repeat(r.rating)}</span> <span style={{ color: r.sentiment === "negative" ? "#e74c3c" : r.sentiment === "positive" ? "#27ae60" : "#888" }}>[{r.sentiment}]</span>
          <p style={{ margin: "4px 0", color: "#555" }}>{r.content || "(无内容)"}</p>
          <small style={{ color: "#999" }}>{r.created_at?.slice(0,16)}</small>
        </div>
      ))}
    </div>
  );
}

function StoreTab() {
  const [store, setStore] = useState<any>(null);
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({ name: "", address: "", opening_time: "", closing_time: "" });
  useEffect(() => { fetchAdminStore().then(s => { setStore(s); setForm({ name: s.name||"", address: s.address||"", opening_time: s.opening_time||"", closing_time: s.closing_time||"" }); }); }, []);
  const save = async () => { await updateStore(form); setEdit(false); fetchAdminStore().then(s => { setStore(s); setForm({ name: s.name||"", address: s.address||"", opening_time: s.opening_time||"", closing_time: s.closing_time||"" }); }); };
  if (!store) return <div>加载中...</div>;
  return (
    <div>
      <h2>门店信息</h2>
      {!edit ? (
        <div style={{ background: "#fff", padding: 16, borderRadius: 8 }}>
          <p><strong>{store.name}</strong></p><p>{store.address}</p>
          <p>营业: {store.opening_time} ~ {store.closing_time}</p>
          <button type="button" onClick={() => setEdit(true)} style={btnGreen}>✏️ 编辑</button>
        </div>
      ) : (
        <div style={{ background: "#fff", padding: 16, borderRadius: 8 }}>
          <input value={form.name} onChange={e => setForm({...form, name: e.target.value})} style={{...inputStyle, display:"block", marginBottom:8}} placeholder="店名" />
          <input value={form.address} onChange={e => setForm({...form, address: e.target.value})} style={{...inputStyle, display:"block", marginBottom:8}} placeholder="地址" />
          <input value={form.opening_time} onChange={e => setForm({...form, opening_time: e.target.value})} style={{...inputStyle, display:"block", marginBottom:8}} placeholder="营业开始 HH:MM" />
          <input value={form.closing_time} onChange={e => setForm({...form, closing_time: e.target.value})} style={{...inputStyle, display:"block", marginBottom:8}} placeholder="营业结束 HH:MM" />
          <button type="button" onClick={save} style={btnGreen}>💾 保存</button>
        </div>
      )}
    </div>
  );
}

function KnowledgeAdminTab() {
  const [file, setFile] = useState<File | null>(null);
  const [collection, setCollection] = useState("massage_shop_rules");
  const [force, setForce] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!file) {
      setError("请先选择 PDF 或 Markdown 手册文件");
      return;
    }
    setUploading(true);
    setError("");
    setResult(null);
    try {
      setResult(await uploadStoreManual({ file, collection, force }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <h2>知识库与门店业务手册</h2>
      <div style={{ background: "#fff", padding: 18, borderRadius: 10, marginBottom: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.08)" }}>
        <h3 style={{ marginTop: 0 }}>上传门店业务手册</h3>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          支持 PDF / Markdown。上传后后端会保存文件，并通过 MCP Server 的 ingest_document 工具入库；同一文件已入库时会自动跳过重复处理。
        </p>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="file"
            accept=".pdf,.md,.markdown,application/pdf,text/markdown"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
            style={inputStyle}
          />
          <input
            value={collection}
            onChange={e => setCollection(e.target.value)}
            placeholder="collection"
            style={{ ...inputStyle, width: 210 }}
          />
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#555" }}>
            <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} />
            强制重新入库
          </label>
          <button type="button" onClick={submit} disabled={uploading} style={{ ...btnGreen, opacity: uploading ? 0.65 : 1 }}>
            {uploading ? "入库中..." : "上传并入库"}
          </button>
        </div>
        {error && <p style={{ color: "#e74c3c", marginBottom: 0 }}>{error}</p>}
        {result && (
          <div style={{ marginTop: 12, padding: 12, background: result.skipped ? "#fff8e6" : "#eef8f1", borderRadius: 8, fontSize: 13 }}>
            <strong>{result.message}</strong>
            <p style={{ margin: "6px 0 0" }}>文件：{result.file_name}</p>
            <p style={{ margin: "4px 0 0" }}>Collection：{result.collection}</p>
            <p style={{ margin: "4px 0 0" }}>Doc ID：{result.doc_id || "-"}</p>
            <p style={{ margin: "4px 0 0" }}>Chunks：{result.chunk_count}，Images：{result.image_count}</p>
            <p style={{ margin: "4px 0 0", color: "#777" }}>状态：{result.skipped ? "已存在，跳过重复入库" : "完成新入库"}</p>
          </div>
        )}
      </div>
      <KnowledgePanel />
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────

const thStyle: React.CSSProperties = { padding: "8px 12px", textAlign: "left", fontSize: 13, fontWeight: 600 };
const tdStyle: React.CSSProperties = { padding: "8px 12px", fontSize: 13 };
const inputStyle: React.CSSProperties = { padding: "6px 12px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14 };
const btnGreen: React.CSSProperties = { padding: "6px 16px", background: "#27ae60", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 };
const btnRed: React.CSSProperties = { padding: "6px 16px", background: "#e74c3c", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 };
const btnBlue: React.CSSProperties = { padding: "6px 16px", background: "#3498db", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, marginRight: 6 };
const btnGray: React.CSSProperties = { padding: "6px 16px", background: "#95a5a6", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, marginLeft: 6 };
