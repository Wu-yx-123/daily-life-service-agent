// 作用：React 应用入口，按角色分流：顾客 → ChatPage，商家 → AdminPanel
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { LoginPage } from "../features/auth/LoginPage";
import { AdminPanel } from "../features/admin/AdminPanel";
import { ChatPage } from "../features/chat/ChatPage";
import "./styles.css";

function App() {
  const [user, setUser] = useState<any>(() => {
    const saved = sessionStorage.getItem("massageops_user");
    return saved ? JSON.parse(saved) : null;
  });

  const handleLogin = (u: any) => {
    sessionStorage.setItem("massageops_user", JSON.stringify(u));
    setUser(u);
  };
  const handleLogout = () => {
    sessionStorage.removeItem("massageops_user");
    setUser(null);
  };

  if (!user) return <LoginPage onLogin={handleLogin} />;

  if (user.login_as === "merchant") return <AdminPanel onLogout={handleLogout} />;

  return <ChatPage userId={user.user_id} userName={user.nickname || user.username || user.phone} onLogout={handleLogout} />;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
