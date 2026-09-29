import { useEffect, useState } from "react";

export type Mode = "system" | "light" | "dark";

export const ACCENTS = [
  { id: "indigo", label: "Índigo", color: "#4f46e5" },
  { id: "blue", label: "Azul", color: "#2563eb" },
  { id: "teal", label: "Verde-água", color: "#0d9488" },
  { id: "green", label: "Verde", color: "#16a34a" },
  { id: "amber", label: "Âmbar", color: "#d97706" },
  { id: "red", label: "Vermelho", color: "#dc2626" },
  { id: "pink", label: "Rosa", color: "#db2777" },
  { id: "violet", label: "Violeta", color: "#7c3aed" },
  { id: "slate", label: "Grafite", color: "#475569" },
] as const;

export type Accent = (typeof ACCENTS)[number]["id"];

export interface Theme {
  mode: Mode;
  accent: Accent;
}

const KEY = "docchat-theme";
const DEFAULT: Theme = { mode: "system", accent: "indigo" };

/** A preferência fica no navegador de quem usa; sem acesso ao storage, vale o padrão. */
export function loadTheme(): Theme {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (saved && ACCENTS.some((a) => a.id === saved.accent) && ["system", "light", "dark"].includes(saved.mode)) {
      return saved;
    }
  } catch {
    /* storage indisponível ou valor inválido */
  }
  return DEFAULT;
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.mode = theme.mode;
  document.documentElement.dataset.accent = theme.accent;
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(loadTheme);

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(KEY, JSON.stringify(theme));
    } catch {
      /* segue sem salvar */
    }
  }, [theme]);

  return {
    theme,
    setMode: (mode: Mode) => setTheme((t) => ({ ...t, mode })),
    setAccent: (accent: Accent) => setTheme((t) => ({ ...t, accent })),
  };
}
