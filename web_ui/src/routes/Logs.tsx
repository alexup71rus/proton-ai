import { useEffect, useState } from "react";

import { fetchLogs, type LogRow } from "../api";
import { LogCard } from "../components/LogCard";


export function LogsRoute() {
  const [rows, setRows] = useState<LogRow[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  async function loadRows() {
    setState("loading");
    setError(null);
    try {
      const payload = await fetchLogs();
      setRows(payload.rows);
      setState("ready");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unknown error.");
      setState("error");
    }
  }

  useEffect(() => {
    void loadRows();
  }, []);

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Step 04</span>
          <h1>Logs</h1>
          <p>Read routing incidents as material for the next dataset iteration, not as a raw JSON tail.</p>
        </div>
        <div className="page-header__meta page-header__meta--actions">
          <span className="pill">{rows.length} incidents</span>
          <button className="button button--secondary" type="button" onClick={() => void loadRows()}>
            Refresh logs
          </button>
        </div>
      </header>

      {state === "loading" ? (
        <div className="panel panel--soft empty-state">
          <h2>Loading routing incidents</h2>
          <p>Fetching the latest human-readable log rows.</p>
        </div>
      ) : null}

      {state === "error" ? (
        <div className="feedback feedback--error">
          <strong>Could not load logs</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {state === "ready" && rows.length === 0 ? (
        <div className="panel empty-state">
          <h2>No incidents yet</h2>
          <p>Once routing failures are logged, they will appear here as readable cards.</p>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="logs-stack">
          {rows.map((row, index) => (
            <LogCard key={`${row.user}-${index}`} row={row} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
