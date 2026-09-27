import "@fontsource-variable/nunito-sans";
import "./app.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { CONFIG } from "./config";

const raiz = document.getElementById(CONFIG.raizDom);
if (raiz) {
  createRoot(raiz).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
