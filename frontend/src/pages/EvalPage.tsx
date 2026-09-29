import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Download, Loader2, Minus, Pencil, Play, Plus, Trash2, Upload, X } from "lucide-react";
import {
  api,
  type DocumentInfo,
  type EvalCase,
  type EvalCaseInput,
  type EvalRun,
  type EvalRunDetail,
  type EvalSummary,
  type Health,
  type SearchMode,
} from "../api";

const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const dec = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(2));

const METRICS: { key: keyof EvalSummary; label: string; hint: string; format: (v: number | null) => string }[] = [
  { key: "hit_rate", label: "Hit rate", hint: "Perguntas em que a página certa veio entre os trechos recuperados", format: pct },
  { key: "mrr", label: "MRR", hint: "Mean Reciprocal Rank: 1 se a página certa veio em 1º, 0,5 se em 2º…", format: dec },
  { key: "citation_accuracy", label: "Citação correta", hint: "A resposta citou um trecho da página esperada", format: pct },
  { key: "judge_score", label: "Nota do juiz", hint: "LLM compara a resposta com o gabarito (0 a 1)", format: dec },
  { key: "answer_f1", label: "F1 de palavras", hint: "Sobreposição de palavras entre resposta e gabarito", format: dec },
];

function Flag({ value }: { value: boolean | null }) {
  if (value == null) return <Minus size={16} className="muted" />;
  return value ? <Check size={16} className="good" /> : <X size={16} className="bad" />;
}

function Summary({ run }: { run: EvalRun }) {
  return (
    <div className="metrics">
      {METRICS.map((m) => (
        <div key={m.key} className="metric" title={m.hint}>
          <span className="metric-label">{m.label}</span>
          <span className="metric-value">{m.format(run.summary[m.key] as number | null)}</span>
        </div>
      ))}
      <div className="metric" title="Tempo médio por pergunta, incluindo busca e geração">
        <span className="metric-label">Latência média</span>
        <span className="metric-value">{run.summary.avg_latency_ms} ms</span>
      </div>
    </div>
  );
}

function RunsTab({ health }: { health: Health | null }) {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topK, setTopK] = useState<number | "">("");
  const [mode, setMode] = useState<SearchMode | "">("");
  const [useJudge, setUseJudge] = useState(true);

  const load = useCallback(async () => {
    const list = await api.runs();
    setRuns(list);
    return list;
  }, []);

  useEffect(() => {
    load().then((list) => list[0] && api.run(list[0].id).then(setDetail));
  }, [load]);

  async function execute() {
    setRunning(true);
    setError(null);
    try {
      const run = await api.createRun({
        top_k: topK || undefined,
        search_mode: mode || undefined,
        use_judge: useJudge,
      });
      setDetail(run);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  async function remove(id: number) {
    await api.deleteRun(id);
    if (detail?.id === id) setDetail(null);
    await load();
  }

  return (
    <>
      <div className="card run-form">
        <label>
          Busca
          <select value={mode} onChange={(e) => setMode(e.target.value as SearchMode | "")}>
            <option value="">Padrão ({health?.search_mode ?? "…"})</option>
            <option value="hybrid">Híbrida</option>
            <option value="vector">Vetorial</option>
          </select>
        </label>
        <label>
          Trechos (top-k)
          <select value={topK} onChange={(e) => setTopK(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Padrão ({health?.top_k ?? "…"})</option>
            {[1, 3, 5, 8, 10].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={useJudge} onChange={(e) => setUseJudge(e.target.checked)} />
          Usar LLM como juiz
        </label>
        <button className="btn primary" onClick={execute} disabled={running}>
          {running ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
          {running ? "Avaliando…" : "Executar avaliação"}
        </button>
      </div>
      {error && <div className="alert error">{error}</div>}

      {runs.length > 1 && (
        <div className="card">
          <h2>Comparação entre execuções</h2>
          <table className="table compact">
            <thead>
              <tr>
                <th>#</th>
                <th>Configuração</th>
                {METRICS.map((m) => (
                  <th key={m.key} className="num" title={m.hint}>
                    {m.label}
                  </th>
                ))}
                <th className="num">Latência</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className={`clickable${detail?.id === r.id ? " selected" : ""}`} onClick={() => api.run(r.id).then(setDetail)}>
                  <td>{r.id}</td>
                  <td>
                    <span className="badge">{r.config.search_mode}</span> k={r.config.top_k} · {r.config.chat_model}
                  </td>
                  {METRICS.map((m) => (
                    <td key={m.key} className="num">
                      {m.format(r.summary[m.key] as number | null)}
                    </td>
                  ))}
                  <td className="num">{r.summary.avg_latency_ms} ms</td>
                  <td className="actions">
                    <button
                      className="icon-btn danger"
                      title="Excluir execução"
                      onClick={(e) => {
                        e.stopPropagation();
                        remove(r.id);
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detail ? (
        <div className="card">
          <h2>
            Execução #{detail.id}{" "}
            <small className="muted">
              {new Date(detail.created_at).toLocaleString("pt-BR")} · {detail.config.provider} · {detail.config.chat_model} ·{" "}
              {detail.config.embedding_model} · busca {detail.config.search_mode} · k={detail.config.top_k}
            </small>
          </h2>
          <Summary run={detail} />
          <table className="table results">
            <thead>
              <tr>
                <th>Pergunta</th>
                <th>Esperado</th>
                <th>Resposta obtida</th>
                <th title="Página esperada estava entre os trechos recuperados">Recup.</th>
                <th title="Resposta citou a página esperada">Citou</th>
                <th className="num">RR</th>
                <th className="num">Juiz</th>
                <th className="num">F1</th>
              </tr>
            </thead>
            <tbody>
              {detail.results.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.question}
                    {r.expected_page && <div className="muted">pág. esperada {r.expected_page}</div>}
                  </td>
                  <td>{r.expected_answer}</td>
                  <td>
                    {r.answer}
                    <div className="muted">
                      recuperou: {r.retrieved.map((s) => `p.${s.page}`).join(", ") || "nada"}
                    </div>
                  </td>
                  <td className="center">
                    <Flag value={r.retrieval_hit} />
                  </td>
                  <td className="center">
                    <Flag value={r.citation_hit} />
                  </td>
                  <td className="num">{dec(r.reciprocal_rank)}</td>
                  <td className="num" title={r.judge_reason ?? undefined}>
                    {dec(r.judge_score)}
                  </td>
                  <td className="num">{dec(r.answer_f1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">Nenhuma execução ainda. Monte o gabarito e clique em “Executar avaliação”.</div>
      )}
    </>
  );
}

const EMPTY: EvalCaseInput = { question: "", expected_answer: "", document_id: null, expected_page: null };

function CasesTab() {
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [form, setForm] = useState<EvalCaseInput>(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api.cases().then(setCases), []);
  useEffect(() => {
    load();
    api.documents().then(setDocs);
  }, [load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editing) await api.updateCase(editing, form);
      else await api.createCase(form);
      setForm(EMPTY);
      setEditing(null);
      await load();
    } catch (err) {
      setMessage({ kind: "error", text: (err as Error).message });
    }
  }

  async function importFile(f: File) {
    try {
      const items = JSON.parse(await f.text());
      const result = await api.importCases(items);
      setMessage({
        kind: result.skipped.length ? "error" : "ok",
        text:
          `${result.imported} perguntas importadas.` +
          (result.skipped.length ? ` Ignoradas: ${result.skipped.join("; ")}` : ""),
      });
      await load();
    } catch (err) {
      setMessage({ kind: "error", text: `Arquivo inválido: ${(err as Error).message}` });
    }
  }

  async function exportFile() {
    const data = await api.exportCases();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "gabarito.json" });
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <form className="card case-form" onSubmit={save}>
        <h2>{editing ? "Editar pergunta" : "Nova pergunta"}</h2>
        <label>
          Pergunta
          <input value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} required />
        </label>
        <label>
          Resposta esperada
          <textarea
            rows={2}
            value={form.expected_answer}
            onChange={(e) => setForm({ ...form, expected_answer: e.target.value })}
            required
          />
        </label>
        <div className="row">
          <label>
            Documento
            <select
              value={form.document_id ?? ""}
              onChange={(e) => setForm({ ...form, document_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">Qualquer</option>
              {docs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}
                </option>
              ))}
            </select>
          </label>
          <label>
            Página esperada
            <input
              type="number"
              min={1}
              value={form.expected_page ?? ""}
              onChange={(e) => setForm({ ...form, expected_page: e.target.value ? Number(e.target.value) : null })}
            />
          </label>
        </div>
        <div className="row end">
          {editing && (
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setEditing(null);
                setForm(EMPTY);
              }}
            >
              Cancelar
            </button>
          )}
          <button className="btn primary">
            {editing ? <Check size={16} /> : <Plus size={16} />} {editing ? "Salvar" : "Adicionar"}
          </button>
        </div>
      </form>

      {message && <div className={`alert ${message.kind}`}>{message.text}</div>}

      <div className="card">
        <div className="card-header">
          <h2>Gabarito ({cases.length})</h2>
          <div className="row">
            <button className="btn ghost" onClick={() => file.current?.click()}>
              <Upload size={16} /> Importar JSON
            </button>
            <button className="btn ghost" onClick={exportFile} disabled={!cases.length}>
              <Download size={16} /> Exportar
            </button>
            <input
              ref={file}
              type="file"
              accept="application/json"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) importFile(f);
                e.target.value = "";
              }}
            />
          </div>
        </div>
        {cases.length === 0 ? (
          <div className="empty">Nenhuma pergunta. Adicione acima ou importe o arquivo samples/gabarito.json.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Pergunta</th>
                <th>Resposta esperada</th>
                <th>Fonte</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>{c.question}</td>
                  <td>{c.expected_answer}</td>
                  <td className="nowrap">
                    {c.document_filename ?? "qualquer"}
                    {c.expected_page && <span className="badge">pág. {c.expected_page}</span>}
                  </td>
                  <td className="actions">
                    <button
                      className="icon-btn"
                      title="Editar"
                      onClick={() => {
                        setEditing(c.id);
                        setForm({
                          question: c.question,
                          expected_answer: c.expected_answer,
                          document_id: c.document_id,
                          expected_page: c.expected_page,
                        });
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      <Pencil size={14} />
                    </button>
                    <button className="icon-btn danger" title="Excluir" onClick={() => api.deleteCase(c.id).then(load)}>
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export default function EvalPage({ health }: { health: Health | null }) {
  const [tab, setTab] = useState<"runs" | "cases">("runs");
  return (
    <div className="page">
      <header className="page-header">
        <h1>Avaliação</h1>
        <p>
          Roda cada pergunta do gabarito pelo mesmo pipeline do chat e mede a recuperação (a página certa foi encontrada?)
          e a resposta (citou a fonte certa e disse o que o gabarito diz?).
        </p>
      </header>
      <div className="tabs">
        <button className={tab === "runs" ? "on" : ""} onClick={() => setTab("runs")}>
          Execuções
        </button>
        <button className={tab === "cases" ? "on" : ""} onClick={() => setTab("cases")}>
          Gabarito
        </button>
      </div>
      {tab === "runs" ? <RunsTab health={health} /> : <CasesTab />}
    </div>
  );
}
