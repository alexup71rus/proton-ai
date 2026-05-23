import type { LogRow } from "../api";


type LogCardProps = {
  row: LogRow;
};


export function LogCard({ row }: LogCardProps) {
  return (
    <article className="panel log-card">
      <div className="log-card__header">
        <div className="log-card__title">
          <span className="eyebrow">Routing incident</span>
          <h2>{row.user}</h2>
        </div>
        <span className={`status-chip status-chip--${row.result} log-card__status`}>{row.result}</span>
      </div>

      <div className="log-card__section log-card__section--inline">
        <strong>Candidates</strong>
        {row.candidates.length > 0 ? (
          <div className="chips-wrap">
            {row.candidates.map((candidate) => (
              <span key={candidate} className="chip chip--static">
                {candidate}
              </span>
            ))}
          </div>
        ) : (
          <p className="log-card__empty">No candidates captured.</p>
        )}
      </div>

      <div className="log-card__meta">
        <div>
          <span>Error</span>
          <strong>{row.error}</strong>
        </div>
      </div>

      {row.raw_output ? (
        <details className="log-card__details">
          <summary>Show raw model output</summary>
          <pre>{row.raw_output}</pre>
        </details>
      ) : null}
    </article>
  );
}
