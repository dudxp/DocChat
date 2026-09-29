import type { DocumentKind } from "./api";

// Um documento não se divide do mesmo jeito em todo formato, e a tela precisa dizer em quê.
const UNITS: Record<DocumentKind, [string, string]> = {
  pdf: ["página", "páginas"],
  docx: ["seção", "seções"],
  xlsx: ["planilha", "planilhas"],
  pptx: ["slide", "slides"],
  text: ["parte", "partes"],
};

/** "6 páginas", "1 planilha". */
export function unitsLabel(kind: DocumentKind, count: number): string {
  const [one, many] = UNITS[kind] ?? UNITS.text;
  return `${count} ${count === 1 ? one : many}`;
}

/** Espelha o SUPPORTED_EXTENSIONS do back-end; quem recusa de verdade é ele. */
export const ACCEPTED_EXTENSIONS = ".csv,.docx,.markdown,.md,.pdf,.pptx,.txt,.xlsx";
