import { useEffect, useState } from "react";
import ChatWindow from "./components/ChatWindow.jsx";
import AdminPanel from "./components/AdminPanel.jsx";

// Customers only see the chat. Staff open  http://localhost:5173/#admin  to get the Admin tab.
const isAdminUrl = () => window.location.hash === "#admin";

export default function App() {
  const [adminMode, setAdminMode] = useState(isAdminUrl);
  const [tab, setTab] = useState(isAdminUrl() ? "admin" : "chat");

  useEffect(() => {
    const onHash = () => {
      const admin = isAdminUrl();
      setAdminMode(admin);
      setTab(admin ? "admin" : "chat");
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const active = adminMode ? tab : "chat";

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo">🛍️</span>
          <div>
            <h1>ShopEase Support</h1>
            <p>{adminMode ? "Staff area" : "AI assistant with human escalation"}</p>
          </div>
        </div>
        {adminMode && (
          <nav className="tabs">
            <button className={active === "chat" ? "tab active" : "tab"} onClick={() => setTab("chat")}>
              Customer Chat
            </button>
            <button className={active === "admin" ? "tab active" : "tab"} onClick={() => setTab("admin")}>
              Admin
            </button>
          </nav>
        )}
      </header>

      <main className="main">
        {/* ChatWindow stays mounted so the conversation is kept when switching tabs */}
        <div style={{ display: active === "chat" ? "block" : "none" }}>
          <ChatWindow />
        </div>
        {adminMode && active === "admin" && <AdminPanel />}
      </main>
    </div>
  );
}
