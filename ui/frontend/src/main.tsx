import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { DbProvider } from "./db";

// Self-hosted fonts (OFL) — bundled locally by Vite, no network at runtime.
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/600.css";

import "./base.css";

// Apply the persisted theme before first paint (avoids a light flash).
document.documentElement.setAttribute(
  "data-theme",
  localStorage.getItem("gavel.theme") === "dark" ? "dark" : "light",
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <DbProvider>
        <App />
      </DbProvider>
    </BrowserRouter>
  </StrictMode>,
);
