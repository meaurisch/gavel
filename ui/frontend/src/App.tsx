import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { useDb } from "./db";
import { useFetch } from "./hooks";
import { GavelMark } from "./components/GavelMark";
import { Dashboard } from "./pages/Dashboard";
import { GradePicker } from "./pages/GradePicker";
import { GradeSession } from "./pages/GradeSession";
import { JudgeSessionPage } from "./pages/JudgeSession";
import { RevealPage } from "./pages/Reveal";
import { Runs } from "./pages/Runs";
import { Browse } from "./pages/Browse";
import { TrialDetailPage } from "./pages/TrialDetail";
import { ReportPage } from "./pages/Report";

function DbSwitcher({ onReset }: { onReset: (badName: string) => void }) {
  const { db, setDb } = useDb();
  const { data: dbs } = useFetch(() => api.dbs(), []);

  const options = dbs ?? [];
  const defaultName = options.find((d) => d.is_default)?.name;

  // Self-heal a stale selection (e.g. a scratch DB that was deleted, left
  // behind in localStorage, or a typo'd ?db= link): fall back to the server
  // default — and TELL the user, because silently showing the synthetic demo
  // DB where they expected real data is a trap.
  useEffect(() => {
    if (dbs && db !== "" && !dbs.some((d) => d.name === db)) {
      onReset(db);
      setDb("");
    }
  }, [dbs, db, setDb, onReset]);

  return (
    <label className="row" style={{ gap: "var(--space-2)" }} data-testid="db-switcher">
      <span className="xsmall muted">Database</span>
      <select
        className="control"
        style={{ minWidth: "12rem" }}
        value={db}
        onChange={(e) => setDb(e.target.value)}
      >
        <option value="">{defaultName ? `${defaultName} (default)` : "(default)"}</option>
        {options
          .filter((d) => !d.is_default)
          .map((d) => (
            <option key={d.name} value={d.name}>
              {d.name} — {d.n_trials} trials
            </option>
          ))}
      </select>
    </label>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<string>(
    () => localStorage.getItem("gavel.theme") ?? "light",
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gavel.theme", theme);
  }, [theme]);
  return (
    <button
      className="btn sm"
      onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
      title={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
      aria-label="Toggle color theme"
      data-testid="theme-toggle"
    >
      {theme === "light" ? "☾ dark" : "☀ light"}
    </button>
  );
}

export default function App() {
  const [dbResetNotice, setDbResetNotice] = useState<string | null>(null);
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <NavLink to="/" className="wordmark">
          <GavelMark size={22} />
          gavel
        </NavLink>
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Dashboard
          </NavLink>
          <NavLink to="/grade" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Grade
          </NavLink>
          <NavLink to="/runs" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Runs
          </NavLink>
          <NavLink to="/browse" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Browse
          </NavLink>
          <NavLink to="/report" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Report
          </NavLink>
        </div>
        <div className="nav-spacer" />
        <DbSwitcher onReset={setDbResetNotice} />
        <ThemeToggle />
      </nav>
      {dbResetNotice && (
        <div
          className="info-banner spread"
          style={{ borderRadius: 0, borderLeft: "none", borderRight: "none", flex: "none" }}
          data-testid="db-reset-notice"
        >
          <span>
            Database <code>{dbResetNotice}</code> was not found — switched to the default database.
          </span>
          <button className="btn sm ghost" onClick={() => setDbResetNotice(null)}>
            dismiss
          </button>
        </div>
      )}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/grade" element={<GradePicker />} />
        <Route path="/grade/session/:sessionId" element={<GradeSession />} />
        <Route path="/grade/session/:sessionId/reveal" element={<RevealPage />} />
        <Route path="/grade/judge/:sessionId" element={<JudgeSessionPage />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/browse" element={<Browse />} />
        <Route path="/browse/:trialId" element={<TrialDetailPage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route
          path="*"
          element={
            <main className="app-main">
              <div className="empty-state">
                <p style={{ marginTop: 0 }}>Page not found.</p>
                <NavLink className="btn" to="/">← Back to the dashboard</NavLink>
              </div>
            </main>
          }
        />
      </Routes>
    </div>
  );
}
