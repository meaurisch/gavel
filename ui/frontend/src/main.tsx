import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { DbProvider } from "./db";
import "./base.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <DbProvider>
        <App />
      </DbProvider>
    </BrowserRouter>
  </StrictMode>,
);
