import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ClipboardCheck, FileText, Loader2, LogOut, MessageSquare, Users } from "lucide-react";
import { api, type Health } from "../lib/api";
import { useAuth, useUser } from "./auth";
import ThemePicker from "./components/ThemePicker";
import AdminPage from "./pages/AdminPage";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import EvalPage from "./pages/EvalPage";
import LoginPage from "./pages/LoginPage";

const NAV = [
  { to: "/chat", label: "Chat", icon: MessageSquare, admin: false },
  { to: "/documentos", label: "Documentos", icon: FileText, admin: false },
  { to: "/avaliacao", label: "Avaliação", icon: ClipboardCheck, admin: true },
  { to: "/administracao", label: "Administração", icon: Users, admin: true },
];

function Shell() {
  const user = useUser();
  const { logout } = useAuth();
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
          {NAV.filter((n) => user.is_admin || !n.admin).map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <ThemePicker />
        <div className="user-box">
          <div className="user-info">
            <strong>{user.name}</strong>
            <small>{user.is_admin ? "Administrador" : user.areas.map((a) => a.name).join(", ") || "Sem área"}</small>
          </div>
          <button className="icon-btn" onClick={logout} title="Sair">
            <LogOut size={16} />
          </button>
        </div>
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
          {user.is_admin && <Route path="/avaliacao" element={<EvalPage health={health} />} />}
          {user.is_admin && <Route path="/administracao" element={<AdminPage />} />}
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="login">
        <Loader2 className="spin" size={28} />
      </div>
    );
  return user ? <Shell /> : <LoginPage />;
}
