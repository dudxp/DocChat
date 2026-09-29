import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, Loader2, Trash2, Upload } from "lucide-react";
import { api, type DocumentInfo } from "../api";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [messages, setMessages] = useState<{ kind: "ok" | "error"; text: string }[]>([]);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api.documents().then(setDocs), []);
  useEffect(() => {
    load();
  }, [load]);

  async function upload(files: File[]) {
    if (!files.length) return;
    setUploading(true);
    setMessages([]);
    try {
      const result = await api.upload(files);
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

  async function remove(doc: DocumentInfo) {
    if (!confirm(`Excluir "${doc.filename}" e todos os seus trechos?`)) return;
    await api.deleteDocument(doc.id);
    await load();
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Documentos</h1>
        <p>Envie PDFs com texto. Cada página é dividida em trechos, e cada trecho vira um vetor no pgvector.</p>
      </header>

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

      {messages.map((m, i) => (
        <div key={i} className={`alert ${m.kind}`}>
          {m.text}
        </div>
      ))}

      {docs.length === 0 ? (
        <div className="empty">Nenhum documento ainda.</div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Arquivo</th>
                <th className="num">Páginas</th>
                <th className="num">Trechos</th>
                <th className="num">Tamanho</th>
                <th>Enviado em</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <span className="file-name">
                      <FileText size={16} /> {d.filename}
                    </span>
                  </td>
                  <td className="num">{d.num_pages}</td>
                  <td className="num">{d.chunk_count}</td>
                  <td className="num">{formatSize(d.size_bytes)}</td>
                  <td>{new Date(d.created_at).toLocaleString("pt-BR")}</td>
                  <td className="actions">
                    <a className="icon-btn" href={api.fileUrl(d.id)} target="_blank" rel="noreferrer" title="Abrir PDF">
                      <ExternalLink size={16} />
                    </a>
                    <button className="icon-btn danger" onClick={() => remove(d)} title="Excluir">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
