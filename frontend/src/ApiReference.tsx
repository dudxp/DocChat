import { useEffect, useState } from "react";
import { ApiReferenceReact } from "@scalar/api-reference-react";
import "@scalar/api-reference-react/style.css";
import { api, session } from "./api";

function prefersDark() {
  const mode = document.documentElement.dataset.mode;
  if (mode === "dark") return true;
  if (mode === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Acompanha o tema escolhido no DocChat (claro, escuro ou do sistema). */
function useDarkMode() {
  const [dark, setDark] = useState(prefersDark);
  useEffect(() => {
    const update = () => setDark(prefersDark());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-mode"] });
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", update);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", update);
    };
  }, []);
  return dark;
}

interface Prefill {
  token: string;
  username: string;
}

/**
 * A página abre sem login, como qualquer Swagger; quem já entrou no DocChat nesta máquina
 * chega autenticado. Só desenha depois de resolver isso, senão o painel de autenticação
 * nasceria vazio e não seria mais preenchido.
 */
function usePrefill(): Prefill | null {
  const [prefill, setPrefill] = useState<Prefill | null>(null);
  useEffect(() => {
    const token = session.token;
    if (!token) {
      setPrefill({ token: "", username: "" });
      return;
    }
    api
      .me()
      .then((user) => setPrefill({ token, username: user.username }))
      .catch(() => setPrefill({ token: "", username: "" }));
  }, []);
  return prefill;
}

/**
 * Referência da API com Scalar, gerada a partir do /api/openapi.json.
 * O componente vem do npm e entra no build do front, então funciona sem acesso a CDN.
 */
export default function ApiReference() {
  const dark = useDarkMode();
  const prefill = usePrefill();

  if (!prefill) return null;

  return (
    <ApiReferenceReact
      key={dark ? "dark" : "light"}
      configuration={{
        url: "/api/openapi.json",
        darkMode: dark,
        forceDarkModeState: dark ? "dark" : "light",
        hideDarkModeToggle: true,
        withDefaultFonts: false,
        defaultOpenAllTags: false,
        metaData: { title: "DocChat · API" },
        // Sem as ferramentas de desenvolvedor da Scalar, que dependem dos serviços deles.
        showDeveloperTools: "never",
        authentication: {
          preferredSecurityScheme: "OAuth2PasswordBearer",
          securitySchemes: {
            OAuth2PasswordBearer: {
              flows: { password: { token: prefill.token, username: prefill.username } },
            },
          },
        },
        customCss: `
          .scalar-app { --scalar-font: inherit; }
          .light-mode, .dark-mode { --scalar-color-accent: var(--primary); }
        `,
      }}
    />
  );
}
