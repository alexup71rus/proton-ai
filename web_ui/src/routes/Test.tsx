import { useState } from "react";

import { runTest, type TestResponse } from "../api";
import { DebugPanel } from "../components/DebugPanel";


export function TestRoute() {
  const [userText, setUserText] = useState("сделай свет потеплее");
  const [showDebug, setShowDebug] = useState(false);
  const [result, setResult] = useState<TestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function handleRun() {
    setIsRunning(true);
    setError(null);
    try {
      const payload = await runTest(userText, false);
      setResult(payload);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error.");
    } finally {
      setIsRunning(false);
    }
  }

  const isFallback = result?.result.status === "fallback";

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Step 03</span>
          <h1>Test</h1>
          <p>Check the final routing outcome first, then open debug only when you need the internals.</p>
        </div>
        <div className="page-header__meta">
          <span className="pill pill--soft">Clean-first view</span>
          {result ? (
            <span className={`status-chip status-chip--${result.result.status}`}>{result.result.status}</span>
          ) : (
            <span className="pill pill--soft">No result yet</span>
          )}
        </div>
      </header>

      <section className="panel test-panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Request</span>
            <h2>Run the router</h2>
          </div>
          <label className="toggle">
            <input type="checkbox" checked={showDebug} onChange={(event) => setShowDebug(event.target.checked)} />
            <span>Debug</span>
          </label>
        </div>

        <textarea
          className="hero-input"
          value={userText}
          onChange={(event) => setUserText(event.target.value)}
          rows={6}
          placeholder="turn on the lamp"
        />

        <div className="action-bar action-bar--static">
          <div className="action-bar__status">
            <span className="pill pill--soft">Default view stays clean</span>
          </div>
          <div className="action-bar__actions">
            <button className="button button--primary" disabled={isRunning || !userText.trim()} onClick={() => void handleRun()} type="button">
              {isRunning ? "Running..." : "Run test"}
            </button>
          </div>
        </div>
      </section>

      {error ? (
        <div className="feedback feedback--error">
          <strong>Request failed</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {result ? (
        <section className={`panel result-card${isFallback ? " result-card--fallback" : ""}`}>
          <div className="section-heading">
            <div>
              <span className="eyebrow">Result</span>
              <h2>{isFallback ? "Fallback returned" : "Tool call ready"}</h2>
            </div>
            <span className={`status-chip status-chip--${result.result.status}`}>{result.result.status}</span>
          </div>

          {result.result.tool_name ? (
            <div className="result-card__grid">
              <div>
                <span>Tool</span>
                <strong>{result.result.tool_name}</strong>
              </div>
              <div>
                <span>Arguments</span>
                <pre>{JSON.stringify(result.result.arguments, null, 2)}</pre>
              </div>
            </div>
          ) : (
            <div className="empty-state empty-state--compact">
              <p>{result.result.response || "The router fell back instead of selecting a tool."}</p>
            </div>
          )}
        </section>
      ) : null}

      {showDebug && result ? <DebugPanel debug={result.debug} /> : null}
    </section>
  );
}
