import { useState } from "react";

import { runTest, type TestResponse, type WorkspaceModel, type WorkspaceTestSettings } from "../api";
import { DebugPanel } from "../components/DebugPanel";
import { usePersistedTestDraft } from "../usePersistedTestDraft";


type TestRouteProps = {
  selectedModel: WorkspaceModel;
  testSettings: WorkspaceTestSettings;
  onTestSettingsChange: (next: WorkspaceTestSettings) => Promise<void>;
};


function formatResultStatus(status: string): string {
  switch (status) {
    case "tool_call":
      return "tool selected";
    case "fallback":
      return "fallback";
    case "success":
      return "complete";
    case "failed":
      return "failed";
    default:
      return status.split("_").join(" ");
  }
}


export function TestRoute({ selectedModel, testSettings, onTestSettingsChange }: TestRouteProps) {
  const [result, setResult] = useState<TestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const {
    userText,
    setUserText,
    showDebug,
    setShowDebug,
    settingsError,
  } = usePersistedTestDraft({
    testSettings,
    onTestSettingsChange,
  });
  const modelReady = Boolean(selectedModel.model_path && selectedModel.tokenizer_path);

  async function handleRun() {
    setIsRunning(true);
    setError(null);
    try {
      const payload = await runTest({
        user_text: userText,
        model_path: selectedModel.model_path,
        tokenizer_path: selectedModel.tokenizer_path,
      });
      setResult(payload);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error.");
    } finally {
      setIsRunning(false);
    }
  }

  const isFallback = result?.result.status === "fallback";
  const execution = result?.result.execution;

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>Test</h1>
          <p>Run a request against the selected model.</p>
        </div>
      </header>

      {!modelReady ? (
        <section className="panel empty-state test-empty-state">
          <h2>Load a model first</h2>
          <p>The test screen becomes available after you load saved files or finish a training run.</p>
        </section>
      ) : (
        <>
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
                <span className="pill pill--soft">Using {selectedModel.label}</span>
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

          {settingsError ? (
            <div className="feedback feedback--error">
              <strong>Could not save test settings</strong>
              <p>{settingsError}</p>
            </div>
          ) : null}

          {result ? (
            <section className={`panel result-card${isFallback ? " result-card--fallback" : ""}`}>
              <div className="section-heading">
                <div>
                  <span className="eyebrow">Result</span>
                  <h2>{isFallback ? "Fallback returned" : "Tool call ready"}</h2>
                </div>
                <span className={`status-chip status-chip--${result.result.status}`}>{formatResultStatus(result.result.status)}</span>
              </div>

              {result.result.tool_name ? (
                <>
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
                  {execution ? (
                    <div className={`feedback feedback--${execution.error ? "error" : "info"}`}>
                      <strong>{execution.error ? "Execution failed" : "Execution output"}</strong>
                      {execution.error ? <p>{execution.error}</p> : null}
                      {execution.output !== null ? <pre>{JSON.stringify(execution.output, null, 2)}</pre> : null}
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="empty-state empty-state--compact">
                  <p>{result.result.response || "The router fell back instead of selecting a tool."}</p>
                </div>
              )}
            </section>
          ) : null}

          {showDebug && result ? <DebugPanel debug={result.debug} /> : null}
        </>
      )}
    </section>
  );
}
