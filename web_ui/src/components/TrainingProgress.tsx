import type { TrainingStatus } from "../api";


type TrainingProgressProps = {
  status: TrainingStatus | null;
};


function formatMetric(value: number | null | undefined): string {
  if (value == null) {
    return "-";
  }
  return value.toFixed(4);
}


function buildSparkline(values: number[]): string | null {
  if (values.length < 2) {
    return null;
  }

  const width = 280;
  const height = 90;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / Math.max(values.length - 1, 1);

  return values
    .map((value, index) => {
      const x = index * step;
      const normalized = (value - min) / span;
      const y = height - normalized * height;
      return `${x},${y}`;
    })
    .join(" ");
}


export function TrainingProgress({ status }: TrainingProgressProps) {
  const lossHistory = status?.loss_history ?? [];
  const metrics = status?.metrics ?? {};
  const sparkline = status ? buildSparkline(lossHistory) : null;

  return (
    <section className="panel training-progress">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Progress</span>
          <h2>Training run</h2>
        </div>
        <span className={`status-chip status-chip--${status?.status ?? "idle"}`}>
          {status?.status ?? "idle"}
        </span>
      </div>

      {!status ? (
        <div className="empty-state empty-state--compact">
          <h3>No training state yet</h3>
          <p>Pick a dataset and start a run to see live progress here.</p>
        </div>
      ) : (
        <>
          <div className="metric-grid">
            <div className="metric-card">
              <span>Epoch</span>
              <strong>
                {status.current_epoch ?? 0} / {status.total_epochs ?? 0}
              </strong>
            </div>
            <div className="metric-card">
              <span>Step</span>
              <strong>
                {status.current_step ?? 0} / {status.total_steps ?? 0}
              </strong>
            </div>
            <div className="metric-card">
              <span>Loss</span>
              <strong>{formatMetric(status.loss)}</strong>
            </div>
            <div className="metric-card">
              <span>Checkpoint</span>
              <strong>{status.checkpoint_path ? "Ready" : "Pending"}</strong>
            </div>
          </div>

          <div className="loss-card panel panel--soft">
            <div className="loss-card__header">
              <strong>Loss curve</strong>
              <span>{lossHistory.length} samples</span>
            </div>

            {sparkline ? (
              <svg viewBox="0 0 280 90" className="loss-card__chart" role="img" aria-label="Loss history">
                <polyline
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  points={sparkline}
                />
              </svg>
            ) : (
              <div className="empty-state empty-state--compact">
                <p>Loss history will appear once the run produces enough steps.</p>
              </div>
            )}
          </div>

          <div className="metrics-stack">
            <div className="panel panel--soft metrics-card">
              <strong>Run config</strong>
              <dl>
                <div>
                  <dt>Model</dt>
                  <dd>{status.model_name || "-"}</dd>
                </div>
                <div>
                  <dt>Tokenizer</dt>
                  <dd>{status.tokenizer_name || "-"}</dd>
                </div>
                <div>
                  <dt>Batch size</dt>
                  <dd>{status.batch_size ?? 1}</dd>
                </div>
              </dl>
            </div>

            <div className="panel panel--soft metrics-card">
              <strong>Metrics</strong>
              {Object.keys(metrics).length === 0 ? (
                <p>No metrics yet.</p>
              ) : (
                <dl>
                  {Object.entries(metrics).map(([name, value]) => (
                    <div key={name}>
                      <dt>{name}</dt>
                      <dd>{formatMetric(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </div>

          {status.error ? (
            <div className="feedback feedback--error">
              <strong>Training failed</strong>
              <p>{status.error}</p>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
