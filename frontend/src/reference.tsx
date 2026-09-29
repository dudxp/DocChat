import React from "react";
import ReactDOM from "react-dom/client";
import ApiReference from "./ApiReference";
import "./styles.css";
import { applyTheme, loadTheme } from "./theme";

// Página à parte do aplicativo: sem rotas, sem barra lateral, sem AuthProvider.
applyTheme(loadTheme());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ApiReference />
  </React.StrictMode>,
);
