import type { TrainingStatus } from "../api";
import { formatTrainingStatusLabel } from "../trainingStatus";


export interface TrainingProgressProps {
  status: TrainingStatus | null;
}


function formatMetric(value: number | null | undefined): string {
  if (value == null) {
    return "-";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}


function formatRatio(hit: number, total: number): string {
  if (total <= 0) {
    return "-";
  }
  const rate = (hit / total) * 100;
  return `${hit} / ${total} (${rate.toFixed(1)}%)`;
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
  const invalidCount = Math.max((status?.eval_total ?? 0) - (status?.eval_valid ?? 0), 0);
  const hasRunState = Boolean(status && status.status !== "idle");
  const runStatus = hasRunState && status ? status : null;

  return (
    <section className="panel training-progress">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Progress</span>
          <h2>Training run</h2>
        </div>
        {hasRunState ? (
          <span className={`status-chip status-chip--${status?.status ?? "idle"}`}>
            {formatTrainingStatusLabel(status?.status)}
          </span>
        ) : null}
      </div>

      {!runStatus ? (
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
                {runStatus.current_epoch ?? 0} / {runStatus.total_epochs ?? 0}
              </strong>
            </div>
            <div className="metric-card">
              <span>Step</span>
              <strong>
                {runStatus.current_step ?? 0} / {runStatus.total_steps ?? 0}
              </strong>
            </div>
            <div className="metric-card">
              <span>Loss</span>
              <strong>{formatMetric(runStatus.loss)}</strong>
            </div>
            <div className="metric-card">
              <span>Checkpoint</span>
              <strong>{runStatus.checkpoint_path ? "Ready" : "Pending"}</strong>
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
                  <dd>{runStatus.model_name || "-"}</dd>
                </div>
                <div>
                  <dt>Tokenizer</dt>
                  <dd>{runStatus.tokenizer_name || "-"}</dd>
                </div>
                <div>
                  <dt>Batch size</dt>
                  <dd>{runStatus.batch_size ?? 1}</dd>
                </div>
              </dl>
            </div>

            <div className="panel panel--soft metrics-card">
              <strong>Evaluation</strong>
              {runStatus.eval_total === 0 ? (
                <p>No post-train evaluation yet.</p>
              ) : (
                <dl>
                  <div>
                    <dt>Exact match</dt>
                    <dd>{formatRatio(runStatus.eval_exact, runStatus.eval_total)}</dd>
                  </div>
                  <div>
                    <dt>Valid output</dt>
                    <dd>{formatRatio(runStatus.eval_valid, runStatus.eval_total)}</dd>
                  </div>
                  <div>
                    <dt>Positive rows</dt>
                    <dd>{formatRatio(runStatus.eval_positive_exact, runStatus.eval_positive_total)}</dd>
                  </div>
                  <div>
                    <dt>Fallback rows</dt>
                    <dd>{formatRatio(runStatus.eval_fallback_exact, runStatus.eval_fallback_total)}</dd>
                  </div>
                  <div>
                    <dt>Invalid outputs</dt>
                    <dd>{formatMetric(invalidCount)}</dd>
                  </div>
                </dl>
              )}
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

          {runStatus.error ? (
            <div className="feedback feedback--error">
              <strong>Training failed</strong>
              <p>{runStatus.error}</p>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
