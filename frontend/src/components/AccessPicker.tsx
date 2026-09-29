import { Globe, Lock } from "lucide-react";
import type { Area, DocumentAccess } from "../api";

/** Escolha de quem pode ver um documento: todos, ou só algumas áreas. */
export default function AccessPicker({
  areas,
  value,
  onChange,
}: {
  areas: Area[];
  value: DocumentAccess;
  onChange: (value: DocumentAccess) => void;
}) {
  const toggle = (id: number) =>
    onChange({
      ...value,
      area_ids: value.area_ids.includes(id) ? value.area_ids.filter((x) => x !== id) : [...value.area_ids, id],
    });

  return (
    <div className="access-picker">
      <div className="segmented two">
        <button type="button" className={value.is_global ? "on" : ""} onClick={() => onChange({ ...value, is_global: true })}>
          <Globe size={15} /> Todos
        </button>
        <button type="button" className={!value.is_global ? "on" : ""} onClick={() => onChange({ ...value, is_global: false })}>
          <Lock size={15} /> Só algumas áreas
        </button>
      </div>
      {!value.is_global && (
        <div className="chips">
          {areas.length === 0 && <span className="muted">Cadastre áreas em Administração.</span>}
          {areas.map((a) => (
            <button type="button" key={a.id} className={`chip${value.area_ids.includes(a.id) ? " on" : ""}`} onClick={() => toggle(a.id)}>
              {a.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function AccessBadges({ isGlobal, areas }: { isGlobal: boolean; areas: Area[] }) {
  if (isGlobal)
    return (
      <span className="badge access global">
        <Globe size={12} /> Todos
      </span>
    );
  if (areas.length === 0)
    return (
      <span className="badge access" title="Nenhuma área vinculada: só administradores veem">
        <Lock size={12} /> Só administradores
      </span>
    );
  return (
    <>
      {areas.map((a) => (
        <span key={a.id} className="badge access">
          <Lock size={12} /> {a.name}
        </span>
      ))}
    </>
  );
}
