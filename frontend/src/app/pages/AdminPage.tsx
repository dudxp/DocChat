import { useCallback, useEffect, useState } from "react";
import { Check, Pencil, Plus, Shield, Trash2, X } from "lucide-react";
import { api, type Area, type User } from "../../lib/api";
import { useUser } from "../auth";
import PasswordInput from "../components/PasswordInput";

interface UserForm {
  id: number | null;
  username: string;
  name: string;
  password: string;
  is_admin: boolean;
  area_ids: number[];
}

const EMPTY: UserForm = { id: null, username: "", name: "", password: "", is_admin: false, area_ids: [] };

function UsersSection({ areas }: { areas: Area[] }) {
  const me = useUser();
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState<UserForm>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api.users().then(setUsers), []);
  useEffect(() => {
    load();
  }, [load]);

  const toggleArea = (id: number) =>
    setForm((f) => ({ ...f, area_ids: f.area_ids.includes(id) ? f.area_ids.filter((x) => x !== id) : [...f.area_ids, id] }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const body = { name: form.name, is_admin: form.is_admin, area_ids: form.area_ids };
      if (form.id) await api.updateUser(form.id, { ...body, password: form.password || undefined });
      else await api.createUser({ ...body, username: form.username, password: form.password });
      setForm(EMPTY);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(u: User) {
    if (!confirm(`Excluir o usuário "${u.username}"?`)) return;
    try {
      await api.deleteUser(u.id);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <form className="card case-form" onSubmit={save}>
        <h2>{form.id ? `Editar ${form.username}` : "Novo usuário"}</h2>
        <div className="row">
          <label>
            Usuário (login)
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              disabled={form.id !== null}
              pattern="[a-zA-Z0-9._\-]{3,}"
              title="Pelo menos 3 caracteres: letras, números, ponto, hífen ou sublinhado"
              required
            />
          </label>
          <label>
            Nome
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </label>
          <label>
            {form.id ? "Nova senha (opcional)" : "Senha"}
            <PasswordInput
              value={form.password}
              minLength={6}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required={!form.id}
              autoComplete="new-password"
            />
          </label>
        </div>
        <div className="field">
          <span className="popover-label">Áreas</span>
          <div className="chips">
            {areas.length === 0 && <span className="muted">Cadastre as áreas abaixo primeiro.</span>}
            {areas.map((a) => (
              <button type="button" key={a.id} className={`chip${form.area_ids.includes(a.id) ? " on" : ""}`} onClick={() => toggleArea(a.id)}>
                {a.name}
              </button>
            ))}
          </div>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={form.is_admin}
            disabled={form.id === me.id}
            onChange={(e) => setForm({ ...form, is_admin: e.target.checked })}
          />
          Administrador: vê todos os documentos, envia arquivos, gerencia usuários e roda avaliações
        </label>
        {error && <div className="alert error">{error}</div>}
        <div className="row end">
          {form.id && (
            <button type="button" className="btn ghost" onClick={() => setForm(EMPTY)}>
              Cancelar
            </button>
          )}
          <button className="btn primary">
            {form.id ? <Check size={16} /> : <Plus size={16} />} {form.id ? "Salvar" : "Criar usuário"}
          </button>
        </div>
      </form>

      <div className="card">
        <h2>Usuários ({users.length})</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Login</th>
              <th>Áreas</th>
              <th>Papel</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td className="muted">{u.username}</td>
                <td className="access-cell">
                  {u.areas.length ? u.areas.map((a) => <span key={a.id} className="badge access">{a.name}</span>) : <span className="muted">—</span>}
                </td>
                <td>
                  {u.is_admin ? (
                    <span className="badge access global">
                      <Shield size={12} /> Administrador
                    </span>
                  ) : (
                    "Leitor"
                  )}
                </td>
                <td className="actions">
                  <button
                    className="icon-btn"
                    title="Editar"
                    onClick={() => {
                      setError(null);
                      setForm({
                        id: u.id,
                        username: u.username,
                        name: u.name,
                        password: "",
                        is_admin: u.is_admin,
                        area_ids: u.areas.map((a) => a.id),
                      });
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    <Pencil size={14} />
                  </button>
                  {u.id !== me.id && (
                    <button className="icon-btn danger" title="Excluir" onClick={() => remove(u)}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function AreasSection({ areas, reload }: { areas: Area[]; reload: () => Promise<unknown> }) {
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<{ id: number; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="card">
      <h2>Áreas</h2>
      <p className="muted">
        Cada documento pode ser visível para todos ou só para algumas áreas. Excluir uma área não apaga documentos nem
        usuários, só remove o vínculo.
      </p>
      <form
        className="row area-form"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => api.createArea(name).then(() => setName("")));
        }}
      >
        <input placeholder="Nome da área, ex.: Qualidade" value={name} onChange={(e) => setName(e.target.value)} required />
        <button className="btn primary">
          <Plus size={16} /> Adicionar
        </button>
      </form>
      {error && <div className="alert error">{error}</div>}
      <ul className="area-list">
        {areas.map((a) => (
          <li key={a.id}>
            {editing?.id === a.id ? (
              <>
                <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} autoFocus />
                <button className="icon-btn" title="Salvar" onClick={() => run(() => api.renameArea(a.id, editing.name).then(() => setEditing(null)))}>
                  <Check size={14} />
                </button>
                <button className="icon-btn" title="Cancelar" onClick={() => setEditing(null)}>
                  <X size={14} />
                </button>
              </>
            ) : (
              <>
                <span>{a.name}</span>
                <button className="icon-btn" title="Renomear" onClick={() => setEditing({ id: a.id, name: a.name })}>
                  <Pencil size={14} />
                </button>
                <button
                  className="icon-btn danger"
                  title="Excluir"
                  onClick={() => confirm(`Excluir a área "${a.name}"?`) && run(() => api.deleteArea(a.id))}
                >
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState<"users" | "areas">("users");
  const [areas, setAreas] = useState<Area[]>([]);
  const reload = useCallback(() => api.areas().then(setAreas), []);
  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Administração</h1>
        <p>Usuários, áreas e o que cada área pode consultar.</p>
      </header>
      <div className="tabs">
        <button className={tab === "users" ? "on" : ""} onClick={() => setTab("users")}>
          Usuários
        </button>
        <button className={tab === "areas" ? "on" : ""} onClick={() => setTab("areas")}>
          Áreas ({areas.length})
        </button>
      </div>
      {tab === "users" ? <UsersSection areas={areas} /> : <AreasSection areas={areas} reload={reload} />}
    </div>
  );
}
