import { Fragment, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, Loader2, RotateCcw, Send } from "lucide-react";
import { api, type ChatResponse, type DocumentInfo, type Health, type SearchMode, type Source } from "../../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
  error?: boolean;
}

const SUGGESTIONS = [
  "Qual é a potência do motor da esteira?",
  "Como rearmar depois do botão de emergência?",
  "Em quantos períodos posso dividir as férias?",
  "Qual o valor do vale-refeição?",
];

/** Troca cada [n] da resposta por um botão que destaca a fonte correspondente. */
function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="answer-text">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        return match ? (
          <button key={i} className="cite" onClick={() => onCite(Number(match[1]))}>
            {match[1]}
          </button>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        );
      })}
    </p>
  );
}

function SourceCard({ source, active, id }: { source: Source; active: boolean; id: string }) {
  return (
    <div id={id} className={`source${active ? " active" : ""}${source.cited ? " cited" : ""}`}>
      <div className="source-head">
        <span className="source-number">{source.number}</span>
        <span className="file-name">
          <FileText size={14} /> {source.filename}
        </span>
        <span className="badge">{source.location}</span>
        <span className="muted" title="Similaridade de cosseno com a pergunta">
          {(source.similarity * 100).toFixed(0)}%
        </span>
        <a
          className="icon-btn"
          href={api.fileUrl(source.document_id, source)}
          target="_blank"
          rel="noreferrer"
          title={source.kind === "pdf" ? "Abrir o PDF nesta página" : "Abrir o arquivo original"}
        >
          <ExternalLink size={14} />
        </a>
      </div>
      <p className="source-text">{source.content}</p>
    </div>
  );
}

export default function ChatPage({ health }: { health: Health | null }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
  const [topK, setTopK] = useState<number | null>(null);
  const [mode, setMode] = useState<SearchMode | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.documents().then(setDocs);
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    const history = messages.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    setLoading(true);
    try {
      const response = await api.chat({
        question: q,
        history,
        document_ids: selectedDocs.length ? selectedDocs : null,
        top_k: topK ?? undefined,
        search_mode: mode ?? undefined,
      });
      setMessages((m) => [...m, { role: "assistant", content: response.answer, response }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: (err as Error).message, error: true }]);
    } finally {
      setLoading(false);
    }
  }

  function cite(messageIndex: number, n: number) {
    const id = `src-${messageIndex}-${n}`;
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const toggleDoc = (id: number) =>
    setSelectedDocs((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <div className="chat">
      <div className="chat-toolbar">
        <div className="doc-filter">
          <span className="muted">Buscar em:</span>
          <button className={`chip${selectedDocs.length === 0 ? " on" : ""}`} onClick={() => setSelectedDocs([])}>
            Todos
          </button>
          {docs.map((d) => (
            <button key={d.id} className={`chip${selectedDocs.includes(d.id) ? " on" : ""}`} onClick={() => toggleDoc(d.id)}>
              {d.filename}
            </button>
          ))}
        </div>
        <div className="chat-settings">
          <label>
            Busca
            <select value={mode ?? ""} onChange={(e) => setMode((e.target.value || null) as SearchMode | null)}>
              <option value="">Padrão ({health?.search_mode ?? "…"})</option>
              <option value="hybrid">Híbrida</option>
              <option value="vector">Vetorial</option>
            </select>
          </label>
          <label>
            Trechos
            <select value={topK ?? ""} onChange={(e) => setTopK(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Padrão ({health?.top_k ?? "…"})</option>
              {[3, 5, 8, 10].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <button className="btn ghost" onClick={() => setMessages([])} disabled={!messages.length}>
            <RotateCcw size={16} /> Nova conversa
          </button>
        </div>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome">
            <h1>Pergunte aos seus documentos</h1>
            <p>
              Cada resposta indica de qual trecho e de qual página a informação saiu.{" "}
              {docs.length === 0 && "Comece enviando um PDF na aba Documentos."}
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion" onClick={() => ask(s)} disabled={!docs.length}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="bubble user">
              {m.content}
            </div>
          ) : (
            <div key={i} className={`bubble assistant${m.error ? " error" : ""}`}>
              {m.response ? <AnswerText text={m.content} onCite={(n) => cite(i, n)} /> : <p>{m.content}</p>}
              {m.response && m.response.search_query !== messages[i - 1]?.content && (
                <small className="muted">Busca feita com: “{m.response.search_query}”</small>
              )}
              {m.response && m.response.sources.length > 0 && (
                <div className="sources">
                  {m.response.sources
                    .filter((s) => s.cited)
                    .map((s) => (
                      <SourceCard key={s.number} id={`src-${i}-${s.number}`} source={s} active={active === `src-${i}-${s.number}`} />
                    ))}
                  {m.response.sources.some((s) => !s.cited) && (
                    <details>
                      <summary>
                        Outros trechos recuperados ({m.response.sources.filter((s) => !s.cited).length}) ·{" "}
                        {m.response.latency_ms} ms
                      </summary>
                      {m.response.sources
                        .filter((s) => !s.cited)
                        .map((s) => (
                          <SourceCard key={s.number} id={`src-${i}-${s.number}`} source={s} active={active === `src-${i}-${s.number}`} />
                        ))}
                    </details>
                  )}
                </div>
              )}
            </div>
          ),
        )}
        {loading && (
          <div className="bubble assistant loading">
            <Loader2 className="spin" size={16} /> Buscando nos documentos…
          </div>
        )}
        <div ref={bottom} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <textarea
          value={question}
          placeholder="Faça uma pergunta sobre os documentos…"
          rows={1}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask(question);
            }
          }}
        />
        <button className="btn primary" disabled={loading || !question.trim()} title="Enviar">
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
