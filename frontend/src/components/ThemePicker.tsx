import { useEffect, useRef, useState } from "react";
import { Check, Monitor, Moon, Palette, Sun } from "lucide-react";
import { ACCENTS, type Mode, useTheme } from "../theme";

const MODES: { id: Mode; label: string; icon: typeof Sun }[] = [
  { id: "system", label: "Sistema", icon: Monitor },
  { id: "light", label: "Claro", icon: Sun },
  { id: "dark", label: "Escuro", icon: Moon },
];

export default function ThemePicker() {
  const { theme, setMode, setAccent } = useTheme();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div className="theme-picker" ref={root}>
      <button className="nav-item theme-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Palette size={18} />
        <span>Aparência</span>
        <span className="accent-dot" />
      </button>

      {open && (
        <div className="theme-popover" role="dialog" aria-label="Aparência">
          <span className="popover-label">Tema</span>
          <div className="segmented">
            {MODES.map(({ id, label, icon: Icon }) => (
              <button key={id} className={theme.mode === id ? "on" : ""} onClick={() => setMode(id)}>
                <Icon size={15} /> {label}
              </button>
            ))}
          </div>

          <span className="popover-label">Cor de destaque</span>
          <div className="swatches">
            {ACCENTS.map((a) => (
              <button
                key={a.id}
                className={`swatch${theme.accent === a.id ? " on" : ""}`}
                style={{ background: a.color }}
                title={a.label}
                aria-label={a.label}
                aria-pressed={theme.accent === a.id}
                onClick={() => setAccent(a.id)}
              >
                {theme.accent === a.id && <Check size={14} />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
