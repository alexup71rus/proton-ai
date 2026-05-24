import { useEffect, useState } from "react";

import {
  fetchDatasets,
  fetchTrainingStatus,
  getDatasetDownloadUrl,
  startTraining,
  validateDataset,
  type DatasetSummary,
  type TrainingStatus,
  type WorkspaceModel,
  type WorkspaceTrainingSettings,
} from "../api";
import { TrainingProgress } from "../components/TrainingProgress";


type Notice = {
  tone: "success" | "error" | "info";
  title: string;
  body?: string;
};


type DatasetTrainingRouteProps = {
  selectedModel: WorkspaceModel;
  trainingSettings: WorkspaceTrainingSettings;
  onTrainingSettingsChange: (next: WorkspaceTrainingSettings) => Promise<void>;
  onModelResolved: (status: TrainingStatus) => void;
};


function formatDatasetSource(source: DatasetSummary["source"]): string {
  switch (source) {
    case "tools_bootstrap":
      return "tools bootstrap";
    case "logs_draft":
      return "logs draft";
    case "manual":
      return "manual";
    default:
      return "imported";
  }
}


function formatModelMode(mode: WorkspaceModel["mode"]): string {
  return mode === "loaded" ? "loaded files" : "draft";
}


function formatTrainingStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case "running":
      return "running";
    case "completed":
    case "success":
      return "complete";
    case "failed":
      return "failed";
    case "idle":
    case undefined:
    case null:
      return "no run yet";
    default:
      return status.split("_").join(" ");
  }
}


function formatDatasetFile(status: TrainingStatus | null, fallbackName: string): string {
  if (status?.dataset_path) {
    return status.dataset_path.split("/").pop() || fallbackName;
  }
  return fallbackName;
}


function formatSha(sha: string | null | undefined): string {
  if (!sha) {
    return "pending";
  }
  return sha.slice(0, 12);
}


export function DatasetTrainingRoute({
  selectedModel,
  trainingSettings,
  onTrainingSettingsChange,
  onModelResolved,
}: DatasetTrainingRouteProps) {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const selectedDataset = trainingSettings.dataset_name;
  const epochs = trainingSettings.epochs;
  const batchSize = trainingSettings.batch_size;

  async function persistTrainingSettings(next: WorkspaceTrainingSettings) {
    try {
      await onTrainingSettingsChange(next);
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Could not save workspace settings",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    }
  }

  async function loadScreen() {
    setLoadState("loading");
    try {
      const [datasetsPayload, statusPayload] = await Promise.all([
        fetchDatasets(),
        fetchTrainingStatus(),
      ]);
      const nextSelectedDataset = datasetsPayload.datasets.some((dataset) => dataset.name === selectedDataset)
        ? selectedDataset
        : datasetsPayload.datasets[0]?.name || "";
      setDatasets(datasetsPayload.datasets);
      setStatus(statusPayload);
      setLoadState("ready");
      if (nextSelectedDataset && nextSelectedDataset !== selectedDataset) {
        void persistTrainingSettings({
          ...trainingSettings,
          dataset_name: nextSelectedDataset,
        });
      }
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Could not load dataset or training state",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
      setLoadState("error");
    }
  }

  useEffect(() => {
    void loadScreen();
  }, []);

  useEffect(() => {
    if (status?.status !== "running") {
      return undefined;
    }

    const interval = window.setInterval(() => {
      void fetchTrainingStatus().then((payload) => {
        setStatus(payload);
        if (payload.model_path && payload.tokenizer_path) {
          onModelResolved(payload);
        }
      }).catch(() => undefined);
    }, 1200);

    return () => window.clearInterval(interval);
  }, [onModelResolved, status?.status]);

  async function reloadDatasets(preserveSelection = true) {
    const payload = await fetchDatasets();
    setDatasets(payload.datasets);
    const nextSelectedDataset = preserveSelection && payload.datasets.some((dataset) => dataset.name === selectedDataset)
      ? selectedDataset
      : payload.datasets[0]?.name ?? "";
    if (nextSelectedDataset !== selectedDataset) {
      await onTrainingSettingsChange({
        ...trainingSettings,
        dataset_name: nextSelectedDataset,
      });
    }
  }


  async function handleValidateDataset(datasetName: string) {
    setNotice(null);
    try {
      const report = await validateDataset(datasetName);
      await reloadDatasets(true);
      setNotice({
        tone: report.status === "valid" ? "success" : "error",
        title: report.status === "valid" ? "Dataset is valid" : "Dataset has validation issues",
        body: report.status === "valid"
          ? `${datasetName} passed validation with ${report.row_count} rows.`
          : `${report.issue_count} issues found in ${datasetName}.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Validation failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    }
  }


  async function handleStartTraining() {
    if (!selectedDataset) {
      return;
    }

    setIsStarting(true);
    setNotice(null);
    try {
      const payload = await startTraining({
        dataset_name: selectedDataset,
        epochs,
        batch_size: batchSize,
        model_name: selectedModel.model_name,
        tokenizer_name: selectedModel.tokenizer_name,
        output_root_dir: selectedModel.output_root_dir,
        artifact_name: selectedModel.artifact_name,
        resume_model_path: selectedModel.mode === "loaded" ? selectedModel.model_path : null,
        resume_tokenizer_path: selectedModel.mode === "loaded" ? selectedModel.tokenizer_path : null,
        hidden_dim: selectedModel.hidden_dim,
        num_layers: selectedModel.num_layers,
        num_heads: selectedModel.num_heads,
      });
      setStatus(payload);
      if (payload.model_path && payload.tokenizer_path) {
        onModelResolved(payload);
      }
      setNotice({
        tone: "success",
        title: "Training started",
        body: `Run launched for ${selectedDataset}.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Training could not start",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsStarting(false);
    }
  }

  const selectedDatasetDetails = datasets.find((dataset) => dataset.name === selectedDataset) ?? null;
  const hasDatasets = datasets.length > 0;
  const isRunning = status?.status === "running";
  const datasetFileLabel = selectedDataset ? formatDatasetFile(status, selectedDataset) : "-";
  const datasetRows = status?.dataset_path && status.dataset_row_count > 0
    ? status.dataset_row_count
    : selectedDatasetDetails?.row_count ?? 0;
  const datasetSha = selectedDatasetDetails?.sha1
    ? formatSha(selectedDatasetDetails.sha1)
    : status?.dataset_path && datasetFileLabel === selectedDataset
      ? formatSha(status.dataset_sha1)
      : "pending";
  const canStartTraining = Boolean(
    selectedDataset.trim()
    && selectedModel.output_root_dir.trim()
    && selectedModel.artifact_name.trim()
    && !isRunning
    && !isStarting
  );

  if (loadState === "loading") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <h1>Dataset + Training</h1>
            <p>Load the dataset library and the current run state.</p>
          </div>
        </header>
        <div className="panel panel--soft empty-state">
          <h2>Loading workflow state</h2>
          <p>Fetching available datasets and training progress from the backend.</p>
        </div>
      </section>
    );
  }

  if (loadState === "error") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <h1>Dataset + Training</h1>
            <p>Select a dataset and use the active model from the header for train or fine-tune.</p>
          </div>
        </header>
        {notice ? (
          <div className={`feedback feedback--${notice.tone}`}>
            <strong>{notice.title}</strong>
            {notice.body ? <p>{notice.body}</p> : null}
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>Dataset + Training</h1>
          <p>Choose a dataset and start training.</p>
        </div>
        <div className="page-header__meta">
          <span className="pill">{datasets.length} discovered files</span>
        </div>
      </header>

      {notice ? (
        <div className={`feedback feedback--${notice.tone}`}>
          <strong>{notice.title}</strong>
          {notice.body ? <p>{notice.body}</p> : null}
        </div>
      ) : null}

      <div className="dataset-training-layout">
        <div className="dataset-training-main">
          <section className="panel dataset-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Dataset</span>
                <h2>Choose training file</h2>
              </div>
              <button className="button button--secondary" type="button" onClick={() => void reloadDatasets()}>
                Refresh files
              </button>
            </div>

            <div className="tool-editor__grid">
              <label className="field field--wide">
                <span>Dataset file</span>
                <select
                  className="input"
                  value={selectedDataset}
                  disabled={isRunning || !hasDatasets}
                  onChange={(event) => void persistTrainingSettings({
                    ...trainingSettings,
                    dataset_name: event.target.value,
                  })}
                >
                  {hasDatasets ? null : <option value="">No datasets found</option>}
                  {datasets.map((dataset) => (
                    <option key={dataset.name} value={dataset.name}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {selectedDatasetDetails ? (
              <div className="dataset-summary panel panel--soft">
                <div>
                  <span>File</span>
                  <strong>{datasetFileLabel}</strong>
                </div>
                <div>
                  <span>Source</span>
                  <strong>{formatDatasetSource(selectedDatasetDetails.source)}</strong>
                </div>
                <div>
                  <span>Rows</span>
                  <strong>{datasetRows}</strong>
                </div>
                <div>
                  <span>SHA1</span>
                  <strong>{datasetSha}</strong>
                </div>
                <div>
                  <span>Validation</span>
                  <strong>{selectedDatasetDetails.validation_status}</strong>
                </div>
                <div>
                  <span>Issues</span>
                  <strong>{selectedDatasetDetails.issue_count}</strong>
                </div>
              </div>
            ) : (
              <p className="page-note">Refresh files if the dataset you expect is missing from the picker.</p>
            )}

            <div className="action-bar action-bar--static">
              <div className="action-bar__status">
                {selectedDataset ? (
                  <span className="pill">{selectedDataset}</span>
                ) : (
                  <span className="pill pill--warning">Choose a dataset file</span>
                )}
              </div>
              <div className="action-bar__actions">
                <button className="button button--secondary" type="button" disabled={!selectedDataset.trim()} onClick={() => void handleValidateDataset(selectedDataset)}>
                  Validate
                </button>
                {selectedDatasetDetails ? (
                  <a className="button button--secondary" href={getDatasetDownloadUrl(selectedDatasetDetails.name)}>
                    Export
                  </a>
                ) : null}
              </div>
            </div>
          </section>

          <section className="panel training-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Training</span>
                <h2>{selectedModel.mode === "loaded" ? "Fine-tune selected model" : "Train selected model"}</h2>
              </div>
            </div>

            <div className="dataset-summary panel panel--soft">
              <div>
                <span>Mode</span>
                <strong>{formatModelMode(selectedModel.mode)}</strong>
              </div>
              <div>
                <span>Save root</span>
                <strong>{selectedModel.output_root_dir}</strong>
              </div>
              <div>
                <span>Save as</span>
                <strong>{selectedModel.artifact_name}</strong>
              </div>
              <div>
                <span>Shape</span>
                <strong>{selectedModel.hidden_dim} / {selectedModel.num_layers} / {selectedModel.num_heads}</strong>
              </div>
              <div>
                <span>Checkpoint</span>
                <strong>{selectedModel.model_path ? "ready" : "not saved yet"}</strong>
              </div>
            </div>

            <div className="tool-editor__grid">
              <label className="field">
                <span>Epochs</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  value={epochs}
                  disabled={isRunning}
                  onChange={(event) => void persistTrainingSettings({
                    ...trainingSettings,
                    epochs: Number(event.target.value) || 1,
                  })}
                />
              </label>

              <label className="field">
                <span>Batch size</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  value={batchSize}
                  disabled={isRunning}
                  onChange={(event) => void persistTrainingSettings({
                    ...trainingSettings,
                    batch_size: Number(event.target.value) || 1,
                  })}
                />
              </label>
            </div>

            <div className="action-bar action-bar--static">
              <div className="action-bar__status">
                {selectedDataset ? (
                  <span className="pill">{selectedDataset}</span>
                ) : (
                  <span className="pill pill--warning">Choose a dataset first</span>
                )}
              </div>
              <div className="action-bar__actions">
                <button
                  className="button button--primary"
                  disabled={!canStartTraining}
                  onClick={() => void handleStartTraining()}
                  type="button"
                >
                  {isStarting ? "Starting..." : isRunning ? "Training in progress" : "Start training"}
                </button>
              </div>
            </div>
          </section>
        </div>

        <TrainingProgress status={status} />
      </div>
    </section>
  );
}
