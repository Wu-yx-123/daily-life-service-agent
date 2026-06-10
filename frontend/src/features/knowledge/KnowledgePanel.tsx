// 作用：知识库面板——检索 + 浏览 collection + 查看文档详情。
import { BookOpen, Search, FolderOpen, FileText } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { queryKnowledge, fetchKnowledgeCollections, fetchKnowledgeDocument } from "../../api/client";
import type { KnowledgeAnswer } from "../../types/agent";

export function KnowledgePanel() {
  const [query, setQuery] = useState("退款政策");
  const [answer, setAnswer] = useState<KnowledgeAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [collections, setCollections] = useState<any[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<any>(null);
  const [view, setView] = useState<"search" | "collections">("search");

  useEffect(() => {
    fetchKnowledgeCollections().then(setCollections).catch(() => {});
  }, []);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try { setAnswer(await queryKnowledge({ query })); } finally { setLoading(false); }
  }

  async function handleDocClick(docId: string) {
    setLoading(true);
    try { setSelectedDoc(await fetchKnowledgeDocument(docId)); } finally { setLoading(false); }
  }

  return (
    <section style={{ padding: 12, background: "#fff", borderRadius: 8, fontSize: 13 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>📚 知识库</h3>
        <div style={{ display: "flex", gap: 4 }}>
          <button type="button" onClick={() => setView("search")} style={tabStyle(view === "search")}>🔍 搜索</button>
          <button type="button" onClick={() => setView("collections")} style={tabStyle(view === "collections")}>📂 目录</button>
        </div>
      </div>

      {view === "search" && (
        <>
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            <input value={query} onChange={e => setQuery(e.target.value)}
              style={{ flex: 1, padding: "6px 10px", border: "1px solid #ddd", borderRadius: 6, fontSize: 13 }} />
            <button type="submit" disabled={loading}
              style={{ padding: "6px 12px", background: "#667eea", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>
              <Search size={14} />
            </button>
          </form>
          {answer ? (
            <div style={{ background: "#f8f9fa", padding: 10, borderRadius: 6 }}>
              <p style={{ margin: "0 0 8px", lineHeight: 1.5 }}>{answer.answer?.slice(0, 300)}</p>
              {answer.evidence?.map((e: any, i: number) => (
                <div key={i} style={{ fontSize: 11, color: "#888", marginTop: 4, cursor: "pointer" }}
                     onClick={() => handleDocClick(e.chunk_id || e.id)}>
                  📄 {e.source_file || e.title} [{e.doc_type || e.category}] {(e.score * 100).toFixed(0)}%
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "#aaa", fontSize: 12 }}>输入关键词搜索知识库。</p>
          )}
        </>
      )}

      {view === "collections" && (
        <div>
          {collections.length === 0 && <p style={{ color: "#aaa", fontSize: 12 }}>加载中…</p>}
          {collections.map((c: any) => (
            <div key={c.name || c.id} style={{ padding: "8px 0", borderBottom: "1px solid #eee" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <FolderOpen size={14} color="#667eea" />
                <strong>{c.name || c.id}</strong>
                {c.document_count !== undefined && (
                  <span style={{ fontSize: 11, color: "#888" }}>({c.document_count} 篇)</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedDoc && (
        <div style={{ marginTop: 10, padding: 10, background: "#f0f4ff", borderRadius: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong style={{ fontSize: 13 }}>📄 文档详情</strong>
            <button type="button" onClick={() => setSelectedDoc(null)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14 }}>✕</button>
          </div>
          {selectedDoc.title && <p style={{ margin: "4px 0" }}>标题: {selectedDoc.title}</p>}
          {selectedDoc.summary && <p style={{ color: "#555", fontSize: 12 }}>{selectedDoc.summary?.slice(0, 200)}</p>}
          {selectedDoc.source_path && <p style={{ fontSize: 11, color: "#888" }}>路径: {selectedDoc.source_path}</p>}
          {selectedDoc.tags && <p style={{ fontSize: 11, color: "#888" }}>标签: {Array.isArray(selectedDoc.tags) ? selectedDoc.tags.join(", ") : selectedDoc.tags}</p>}
          {selectedDoc.chunk_count !== undefined && <p style={{ fontSize: 11, color: "#888" }}>Chunks: {selectedDoc.chunk_count}</p>}
        </div>
      )}
    </section>
  );
}

const tabStyle = (active: boolean): React.CSSProperties => ({
  padding: "3px 10px", border: active ? "1px solid #667eea" : "1px solid #ddd",
  borderRadius: 4, background: active ? "#667eea" : "#fff",
  color: active ? "#fff" : "#666", cursor: "pointer", fontSize: 12,
});
