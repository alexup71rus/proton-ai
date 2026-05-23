import { useEffect, useRef, useState } from "react";

import {
  fetchDatasets,
  fetchTrainingStatus,
  generateDataset,
  getDatasetDownloadUrl,
  importDataset,
  startTraining,
  type DatasetSummary,
  type TrainingStatus,
} from "../api";
import { TrainingProgress } from "../components/TrainingProgress";


type Notice = {
  tone: "success" | "error" | "info";
  title: string;
  body?: string;
};


export function DatasetTrainingRoute() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [modelName, setModelName] = useState("tiny-router");
  const [tokenizerName, setTokenizerName] = useState("sentencepiece-bpe");
  const [epochs, setEpochs] = useState(1);
  const [batchSize, setBatchSize] = useState(1);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function loadScreen() {
    setLoadState("loading");
    try {
      const [datasetsPayload, statusPayload] = await Promise.all([
        fetchDatasets(),
        fetchTrainingStatus(),
      ]);
      setDatasets(datasetsPayload.datasets);
      setSelectedDataset((current) => current || datasetsPayload.datasets[0]?.name || "");
      setStatus(statusPayload);
      setLoadState("ready");
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
      void fetchTrainingStatus().then(setStatus).catch(() => undefined);
    }, 1200);

    return () => window.clearInterval(interval);
  }, [status?.status]);

  async function reloadDatasets(preserveSelection = true) {
    const payload = await fetchDatasets();
    setDatasets(payload.datasets);
    setSelectedDataset((current) => {
      if (preserveSelection && current && payload.datasets.some((dataset) => dataset.name === current)) {
        return current;
      }
      return payload.datasets[0]?.name ?? "";
    });
  }

  async function handleImport(file: File) {
    setIsImporting(true);
    setNotice(null);
    try {
      const payload = await importDataset(file);
      await reloadDatasets(false);
      setSelectedDataset(payload.dataset.name);
      setNotice({
        tone: "success",
        title: "Dataset imported",
        body: `${payload.dataset.name} is now available for training.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Dataset import failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleGenerate() {
    setIsGenerating(true);
    setNotice(null);
    try {
      const payload = await generateDataset();
      await reloadDatasets(false);
      setSelectedDataset(payload.dataset.name);
      setNotice({
        tone: "success",
        title: "Synthetic dataset generated",
        body: `${payload.rows_written} rows written to ${payload.dataset.name}.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Dataset generation failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsGenerating(false);
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
        model_name: modelName,
        tokenizer_name: tokenizerName,
      });
      setStatus(payload);
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
  const isRunning = status?.status === "running";

  if (loadState === "loading") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <span className="eyebrow">Step 02</span>
            <h1>Dataset + Training</h1>
            <p>Load datasets and the current run state.</p>
          </div>
        </header>
        <div className="panel panel--soft empty-state">
          <h2>Loading workflow state</h2>
          <p>Fetching datasets and training progress from the new backend.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Step 02</span>
          <h1>Dataset + Training</h1>
          <p>Pick a dataset, generate or import new rows, then watch the run like a real workflow.</p>
        </div>
        <div className="page-header__meta">
          <span className="pill">{datasets.length} datasets</span>
          <span className={`status-chip status-chip--${status?.status ?? "idle"}`}>{status?.status ?? "idle"}</span>
          {selectedDataset ? <span className="pill pill--soft">{selectedDataset}</span> : null}
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
                <h2>Prepare training data</h2>
              </div>
              <button className="button button--secondary" type="button" onClick={() => void reloadDatasets()}>
                Refresh list
              </button>
            </div>

            <div className="dataset-panel__selector">
              <label className="field field--wide">
                <span>Dataset file</span>
                <select
                  className="input"
                  value={selectedDataset}
                  onChange={(event) => setSelectedDataset(event.target.value)}
                >
                  <option value="">Select dataset</option>
                  {datasets.map((dataset) => (
                    <option key={dataset.name} value={dataset.name}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
              </label>

              {selectedDatasetDetails ? (
                <div className="dataset-summary panel panel--soft">
                  <div>
                    <span>Size</span>
                    <strong>{selectedDatasetDetails.size_bytes} bytes</strong>
                  </div>
                  <div>
                    <span>Updated</span>
                    <strong>{new Date(selectedDatasetDetails.updated_at).toLocaleString()}</strong>
                  </div>
                </div>
              ) : (
                <div className="empty-state empty-state--compact">
                  <p>Import a dataset or generate one from the current tools registry.</p>
                </div>
              )}
            </div>

            <div className="dataset-actions">
              <input
                ref={fileInputRef}
                className="visually-hidden"
                type="file"
                accept=".jsonl"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    void handleImport(file);
                  }
                }}
              />
              <button
                className="button button--secondary"
                disabled={isImporting}
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                {isImporting ? "Importing..." : "Import dataset"}
              </button>
              <button
                className="button button--secondary"
                disabled={isGenerating}
                onClick={() => void handleGenerate()}
                type="button"
              >
                {isGenerating ? "Generating..." : "Generate synthetic examples"}
              </button>
              <a
                className={`button button--secondary${selectedDataset ? "" : " button--disabled"}`}
                href={selectedDataset ? getDatasetDownloadUrl(selectedDataset) : undefined}
                onClick={(event) => {
                  if (!selectedDataset) {
                    event.preventDefault();
                  }
                }}
              >
                Export dataset
              </a>
            </div>
          </section>

          <section className="panel training-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Training</span>
                <h2>Launch the next run</h2>
              </div>
            </div>

            <div className="tool-editor__grid">
              <label className="field">
                <span>Model</span>
                <select className="input" value={modelName} onChange={(event) => setModelName(event.target.value)} disabled={isRunning}>
                  <option value="tiny-router">tiny-router</option>
                </select>
              </label>

              <label className="field">
                <span>Tokenizer</span>
                <select className="input" value={tokenizerName} onChange={(event) => setTokenizerName(event.target.value)} disabled={isRunning}>
                  <option value="sentencepiece-bpe">sentencepiece-bpe</option>
                </select>
              </label>

              <label className="field">
                <span>Epochs</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  value={epochs}
                  disabled={isRunning}
                  onChange={(event) => setEpochs(Number(event.target.value) || 1)}
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
                  onChange={(event) => setBatchSize(Number(event.target.value) || 1)}
                />
              </label>
            </div>

            <div className="action-bar action-bar--static">
              <div className="action-bar__status">
                {selectedDataset ? (
                  <span className="pill">Using {selectedDataset}</span>
                ) : (
                  <span className="pill pill--warning">Choose a dataset first</span>
                )}
              </div>
              <div className="action-bar__actions">
                <button
                  className="button button--primary"
                  disabled={!selectedDataset || isStarting || isRunning}
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
