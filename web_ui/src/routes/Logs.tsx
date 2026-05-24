import { useEffect, useState } from "react";

import { exportFailedCases, fetchLogs, type LogRow } from "../api";
import { LogCard } from "../components/LogCard";


export function LogsRoute() {
  const [rows, setRows] = useState<LogRow[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

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

  async function handleExportFailedCases() {
    setIsExporting(true);
    setNotice(null);
    try {
      const payload = await exportFailedCases();
      setNotice(`${payload.rows_written} draft rows exported to ${payload.dataset.name}.`);
    } catch (exportError) {
      setNotice(exportError instanceof Error ? exportError.message : "Unknown error.");
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>Logs</h1>
          <p>Read routing incidents as material for the next dataset iteration, not as a raw JSON tail.</p>
        </div>
        <div className="page-header__meta page-header__meta--actions">
          <span className="pill">{rows.length} incidents</span>
          <button className="button button--secondary" type="button" disabled={isExporting} onClick={() => void handleExportFailedCases()}>
            {isExporting ? "Exporting..." : "Export failed cases"}
          </button>
          <button className="button button--secondary" type="button" onClick={() => void loadRows()}>
            Refresh logs
          </button>
        </div>
      </header>

      {notice ? (
        <div className="feedback feedback--info">
          <strong>Logs export</strong>
          <p>{notice}</p>
        </div>
      ) : null}

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
