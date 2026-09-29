import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ClipboardCheck, FileText, MessageSquare } from "lucide-react";
import { api, type Health } from "./api";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import EvalPage from "./pages/EvalPage";

const NAV = [
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/documentos", label: "Documentos", icon: FileText },
  { to: "/avaliacao", label: "Avaliação", icon: ClipboardCheck },
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setOffline(true));
  }, []);

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>DocChat</span>
        </div>
        <nav>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="model-info">
          {offline && <span className="status error">API indisponível</span>}
          {health && (
            <>
              <span className="status ok">{health.provider}</span>
              <small title="Modelo de chat">{health.chat_model}</small>
              <small title="Modelo de embeddings">{health.embedding_model}</small>
            </>
          )}
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage health={health} />} />
          <Route path="/documentos" element={<DocumentsPage />} />
          <Route path="/avaliacao" element={<EvalPage health={health} />} />
        </Routes>
      </main>
    </div>
  );
}
