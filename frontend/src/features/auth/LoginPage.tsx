import React, { useState } from "react";
import { login } from "../../api/client";

export function LoginPage({ onLogin }: { onLogin: (user: any) => void }) {
  const [loginAs, setLoginAs] = useState<"customer" | "merchant">("customer");
  const [username, setUsername] = useState("customer");
  const [password, setPassword] = useState("Customer@123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const chooseRole = (nextRole: "customer" | "merchant") => {
    setLoginAs(nextRole);
    if (nextRole === "customer") {
      setUsername("customer");
      setPassword("Customer@123");
    } else {
      setUsername("merchant");
      setPassword("Merchant@123");
    }
  };

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      const user = await login({ username, password, login_as: loginAs });
      onLogin(user);
    } catch (e: any) {
      setError(e.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center", height: "100vh",
      background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
    }}>
      <div style={{
        background: "#fff", padding: "40px 36px", borderRadius: 12,
        width: 400, boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
      }}>
        <h1 style={{ textAlign: "center", marginBottom: 4, fontSize: 24 }}>MassageOps</h1>
        <p style={{ textAlign: "center", color: "#888", marginBottom: 24, fontSize: 14 }}>账号密码登录</p>

        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          <button
            type="button"
            onClick={() => chooseRole("customer")}
            style={{
              flex: 1, padding: "12px 8px", border: loginAs === "customer" ? "2px solid #3498db" : "2px solid #eee",
              borderRadius: 8, background: loginAs === "customer" ? "#eaf4fd" : "#fff",
              cursor: "pointer", fontWeight: 600, fontSize: 14,
            }}
          >用户端</button>
          <button
            type="button"
            onClick={() => chooseRole("merchant")}
            style={{
              flex: 1, padding: "12px 8px", border: loginAs === "merchant" ? "2px solid #e67e22" : "2px solid #eee",
              borderRadius: 8, background: loginAs === "merchant" ? "#fef5e7" : "#fff",
              cursor: "pointer", fontWeight: 600, fontSize: 14,
            }}
          >商家端</button>
        </div>

        <label style={{ fontSize: 13, color: "#666" }}>账号</label>
        <input
          value={username}
          onChange={e => setUsername(e.target.value)}
          style={{ width: "100%", padding: "10px 12px", margin: "6px 0 14px", border: "1px solid #ddd", borderRadius: 6, fontSize: 15, boxSizing: "border-box" }}
          placeholder={loginAs === "customer" ? "customer" : "merchant"}
        />

        <label style={{ fontSize: 13, color: "#666" }}>密码</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") void submit(); }}
          style={{ width: "100%", padding: "10px 12px", margin: "6px 0 16px", border: "1px solid #ddd", borderRadius: 6, fontSize: 15, boxSizing: "border-box" }}
          placeholder="请输入密码"
        />

        <div style={{ background: "#f8f9fa", borderRadius: 8, padding: 10, color: "#666", fontSize: 12, lineHeight: 1.6, marginBottom: 14 }}>
          默认用户账号：customer / Customer@123<br />
          默认商家账号：merchant / Merchant@123
        </div>

        {error && <div style={{ color: "#e74c3c", fontSize: 13, marginBottom: 12 }}>{error}</div>}

        <button
          type="button"
          onClick={submit}
          disabled={loading || !username || !password}
          style={{
            width: "100%", padding: "12px", background: loading ? "#bbb" : loginAs === "customer" ? "#3498db" : "#e67e22",
            color: "#fff", border: "none", borderRadius: 6, fontSize: 16, fontWeight: 600,
            cursor: loading || !username || !password ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "登录中..." : loginAs === "customer" ? "进入用户端" : "进入商家端"}
        </button>
      </div>
    </div>
  );
}
