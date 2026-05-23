import type { TestResponse } from "../api";


type DebugPanelProps = {
  debug: TestResponse["debug"];
};


export function DebugPanel({ debug }: DebugPanelProps) {
  return (
    <section className="panel debug-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Debug</span>
          <h2>Routing internals</h2>
        </div>
        <div className="tool-list__meta">
          <span className="pill">Confidence: {debug.confidence}</span>
          <span className="pill pill--soft">Action: {debug.final_action}</span>
        </div>
      </div>

      <div className="debug-grid">
        <div className="panel panel--soft debug-card">
          <strong>Candidate tools</strong>
          <div className="chips-wrap">
            {debug.candidate_tools.map((tool) => (
              <span key={tool} className="chip chip--static">
                {tool}
              </span>
            ))}
          </div>
        </div>

        <div className="panel panel--soft debug-card">
          <strong>Validator result</strong>
          <pre>{JSON.stringify(debug.validator_result, null, 2)}</pre>
        </div>

        <div className="panel panel--soft debug-card debug-card--wide">
          <strong>Raw model output</strong>
          <pre>{debug.raw_model_output || "-"}</pre>
        </div>

        <div className="panel panel--soft debug-card debug-card--wide">
          <strong>Repaired output</strong>
          <pre>{debug.repaired_output || "-"}</pre>
        </div>
      </div>
    </section>
  );
}
