import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ExternalLink, FileText, Loader2, Shield, Trash2, Upload, X } from "lucide-react";
import { api, type Area, type DocumentAccess, type DocumentInfo } from "../api";
import { useUser } from "../auth";
import AccessPicker, { AccessBadges } from "../components/AccessPicker";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

const GLOBAL: DocumentAccess = { is_global: true, area_ids: [] };

export default function DocumentsPage() {
  const user = useUser();
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [access, setAccess] = useState<DocumentAccess>(GLOBAL);
  const [editing, setEditing] = useState<{ id: number; access: DocumentAccess } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [messages, setMessages] = useState<{ kind: "ok" | "error"; text: string }[]>([]);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api.documents().then(setDocs), []);
  useEffect(() => {
    load();
    if (user.is_admin) api.areas().then(setAreas);
  }, [load, user.is_admin]);

  const accessInvalid = !access.is_global && access.area_ids.length === 0;

  async function upload(files: File[]) {
    if (!files.length) return;
    if (accessInvalid) {
      setMessages([{ kind: "error", text: "Escolha ao menos uma área, ou deixe o documento visível para todos." }]);
      return;
    }
    setUploading(true);
    setMessages([]);
    try {
      const result = await api.upload(files, access);
      setMessages([
        ...result.documents.map((d) => ({
          kind: "ok" as const,
          text: `${d.filename}: ${d.num_pages} páginas, ${d.chunk_count} trechos indexados`,
        })),
        ...result.errors.map((e) => ({ kind: "error" as const, text: `${e.filename}: ${e.error}` })),
      ]);
      await load();
    } catch (err) {
      setMessages([{ kind: "error", text: (err as Error).message }]);
    } finally {
      setUploading(false);
    }
  }

  async function saveAccess() {
    if (!editing) return;
    try {
      await api.updateAccess(editing.id, editing.access);
      setEditing(null);
      await load();
    } catch (err) {
      setMessages([{ kind: "error", text: (err as Error).message }]);
    }
  }

  async function remove(doc: DocumentInfo) {
    if (!confirm(`Excluir "${doc.filename}" e todos os seus trechos?`)) return;
    await api.deleteDocument(doc.id);
    await load();
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Documentos</h1>
        <p>
          {user.is_admin
            ? "Envie PDFs com texto e escolha quem pode consultá-los. O que uma área não pode ver nunca entra nas respostas dela."
            : "Documentos que você pode consultar: os da empresa toda e os compartilhados com a sua área."}
        </p>
      </header>

      {user.is_admin && (
        <div className="card upload-card">
          <div className="upload-access">
            <span className="popover-label">Quem pode ver os próximos envios</span>
            <AccessPicker areas={areas} value={access} onChange={setAccess} />
          </div>
          <div
            className={`dropzone${dragging ? " dragging" : ""}`}
            onClick={() => input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              upload(Array.from(e.dataTransfer.files));
            }}
          >
            {uploading ? <Loader2 className="spin" size={28} /> : <Upload size={28} />}
            <strong>{uploading ? "Processando e gerando embeddings…" : "Arraste PDFs aqui ou clique para escolher"}</strong>
            <small>Vários arquivos de uma vez são aceitos</small>
            <input
              ref={input}
              type="file"
              accept="application/pdf"
              multiple
              hidden
              onChange={(e) => {
                upload(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
          </div>
        </div>
      )}

      {messages.map((m, i) => (
        <div key={i} className={`alert ${m.kind}`}>
          {m.text}
        </div>
      ))}

      {docs.length === 0 ? (
        <div className="empty">{user.is_admin ? "Nenhum documento ainda." : "Nenhum documento disponível para a sua área."}</div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Quem vê</th>
                <th className="num">Páginas</th>
                <th className="num">Trechos</th>
                <th className="num">Tamanho</th>
                <th>Enviado em</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {docs.map((d) =>
                editing?.id === d.id ? (
                  <tr key={d.id} className="selected">
                    <td>
                      <span className="file-name">
                        <FileText size={16} /> {d.filename}
                      </span>
                    </td>
                    <td colSpan={5}>
                      <AccessPicker areas={areas} value={editing.access} onChange={(a) => setEditing({ id: d.id, access: a })} />
                    </td>
                    <td className="actions">
                      <button
                        className="icon-btn"
                        title="Salvar"
                        onClick={saveAccess}
                        disabled={!editing.access.is_global && editing.access.area_ids.length === 0}
                      >
                        <Check size={16} />
                      </button>
                      <button className="icon-btn" title="Cancelar" onClick={() => setEditing(null)}>
                        <X size={16} />
                      </button>
                    </td>
                  </tr>
                ) : (
                  <tr key={d.id}>
                    <td>
                      <span className="file-name">
                        <FileText size={16} /> {d.filename}
                      </span>
                    </td>
                    <td className="access-cell">
                      <AccessBadges isGlobal={d.is_global} areas={d.areas} />
                    </td>
                    <td className="num">{d.num_pages}</td>
                    <td className="num">{d.chunk_count}</td>
                    <td className="num">{formatSize(d.size_bytes)}</td>
                    <td>{new Date(d.created_at).toLocaleString("pt-BR")}</td>
                    <td className="actions">
                      <a className="icon-btn" href={api.fileUrl(d.id)} target="_blank" rel="noreferrer" title="Abrir PDF">
                        <ExternalLink size={16} />
                      </a>
                      {user.is_admin && (
                        <>
                          <button
                            className="icon-btn"
                            title="Alterar quem pode ver"
                            onClick={() =>
                              setEditing({ id: d.id, access: { is_global: d.is_global, area_ids: d.areas.map((a) => a.id) } })
                            }
                          >
                            <Shield size={16} />
                          </button>
                          <button className="icon-btn danger" onClick={() => remove(d)} title="Excluir">
                            <Trash2 size={16} />
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
