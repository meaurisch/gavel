import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { useDb } from "./db";
import { useFetch } from "./hooks";
import { Dashboard } from "./pages/Dashboard";
import { GradePicker } from "./pages/GradePicker";
import { GradeSession } from "./pages/GradeSession";
import { RevealPage } from "./pages/Reveal";
import { Runs } from "./pages/Runs";
import { Browse } from "./pages/Browse";
import { TrialDetailPage } from "./pages/TrialDetail";
import { ReportPage } from "./pages/Report";

function DbSwitcher() {
  const { db, setDb } = useDb();
  const { data: dbs } = useFetch(() => api.dbs(), []);

  const options = dbs ?? [];
  const defaultName = options.find((d) => d.is_default)?.name;

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

export default function App() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <NavLink to="/" className="wordmark">
          Tiltyard
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
        <DbSwitcher />
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/grade" element={<GradePicker />} />
        <Route path="/grade/session/:sessionId" element={<GradeSession />} />
        <Route path="/grade/session/:sessionId/reveal" element={<RevealPage />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/browse" element={<Browse />} />
        <Route path="/browse/:trialId" element={<TrialDetailPage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route
          path="*"
          element={
            <main className="app-main">
              <div className="empty-state">Page not found.</div>
            </main>
          }
        />
      </Routes>
    </div>
  );
}
