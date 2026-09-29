import { useEffect, useState } from "react";
import { ApiReferenceReact } from "@scalar/api-reference-react";
import "@scalar/api-reference-react/style.css";
import { session } from "../api";
import { useUser } from "../auth";

function prefersDark() {
  const mode = document.documentElement.dataset.mode;
  if (mode === "dark") return true;
  if (mode === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Acompanha o tema do DocChat (claro, escuro ou do sistema). */
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

/**
 * Referência da API com Scalar, gerada a partir do /api/openapi.json.
 * O componente vem do npm e entra no build do front, então funciona sem acesso a CDN.
 */
export default function ApiReferencePage() {
  const user = useUser();
  const dark = useDarkMode();

  return (
    <div className="api-reference">
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
          // Sem os extras que dependem dos serviços da Scalar (chat com IA, MCP, ferramentas de deploy).
          showDeveloperTools: "never",
          // Já entra autenticado com o login atual do DocChat.
          authentication: {
            preferredSecurityScheme: "OAuth2PasswordBearer",
            securitySchemes: {
              OAuth2PasswordBearer: {
                flows: { password: { token: session.token ?? "", username: user.username } },
              },
            },
          },
          customCss: `
            .scalar-app { --scalar-font: inherit; }
            .light-mode, .dark-mode { --scalar-color-accent: var(--primary); }
          `,
        }}
      />
    </div>
  );
}
