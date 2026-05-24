import { useEffect, useRef, useState } from "react";

import {
  appendDatasetRows,
  bootstrapDataset,
  createManualDataset,
  deleteDataset,
  duplicateDataset,
  fetchDatasetDetails,
  fetchDatasets,
  fetchTrainingStatus,
  getDatasetDownloadUrl,
  importDataset,
  startTraining,
  validateDataset,
  type DatasetDetailResponse,
  type DatasetSummary,
  type TrainingStatus,
} from "../api";
import { TrainingProgress } from "../components/TrainingProgress";


type Notice = {
  tone: "success" | "error" | "info";
  title: string;
  body?: string;
};


const TOOL_CALL_TEMPLATE = `{"tools":[{"name":"tool_name","tags":["tag"]}],"user":"show me tool_name","assistant":{"tool_calls":[{"name":"tool_name","arguments":{}}],"answer":false,"fallback":false}}`;

const FALLBACK_TEMPLATE = `{"tools":[{"name":"get_node_version","tags":["node","node version"]}],"user":"how are you","assistant":{"tool_calls":[],"answer":true,"fallback":true}}`;


function nextDatasetName(prefix: string): string {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
  return `${prefix}-${stamp}.jsonl`;
}


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


export function DatasetTrainingRoute() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [datasetDetails, setDatasetDetails] = useState<DatasetDetailResponse | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isSavingManual, setIsSavingManual] = useState(false);
  const [isAppendingRows, setIsAppendingRows] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [modelName, setModelName] = useState("tiny-router");
  const [tokenizerName, setTokenizerName] = useState("sentencepiece-bpe");
  const [epochs, setEpochs] = useState(1);
  const [batchSize, setBatchSize] = useState(1);
  const [bootstrapDatasetName, setBootstrapDatasetName] = useState(() => nextDatasetName("tools-bootstrap"));
  const [manualDatasetName, setManualDatasetName] = useState(() => nextDatasetName("manual-dataset"));
  const [manualContent, setManualContent] = useState(TOOL_CALL_TEMPLATE);
  const [appendContent, setAppendContent] = useState(TOOL_CALL_TEMPLATE);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function loadDatasetPreview(datasetName: string) {
    if (!datasetName) {
      setDatasetDetails(null);
      return;
    }
    setSelectedDataset(datasetName);
    const payload = await fetchDatasetDetails(datasetName, 8);
    setDatasetDetails(payload);
  }

  async function loadScreen() {
    setLoadState("loading");
    try {
      const [datasetsPayload, statusPayload] = await Promise.all([
        fetchDatasets(),
        fetchTrainingStatus(),
      ]);
      const nextSelectedDataset = selectedDataset || datasetsPayload.datasets[0]?.name || "";
      setDatasets(datasetsPayload.datasets);
      setSelectedDataset(nextSelectedDataset);
      if (nextSelectedDataset) {
        await loadDatasetPreview(nextSelectedDataset);
      } else {
        setDatasetDetails(null);
      }
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
    const nextSelectedDataset = preserveSelection && selectedDataset && payload.datasets.some((dataset) => dataset.name === selectedDataset)
      ? selectedDataset
      : payload.datasets[0]?.name ?? "";
    setSelectedDataset(nextSelectedDataset);
    if (nextSelectedDataset) {
      await loadDatasetPreview(nextSelectedDataset);
    } else {
      setDatasetDetails(null);
    }
  }

  async function handleImport(file: File) {
    setIsImporting(true);
    setNotice(null);
    try {
      const payload = await importDataset(file);
      await reloadDatasets(false);
      setSelectedDataset(payload.dataset.name);
      await loadDatasetPreview(payload.dataset.name);
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

  async function handleBootstrap() {
    setIsBootstrapping(true);
    setNotice(null);
    try {
      const payload = await bootstrapDataset(bootstrapDatasetName);
      await reloadDatasets(false);
      setSelectedDataset(payload.dataset.name);
      await loadDatasetPreview(payload.dataset.name);
      setBootstrapDatasetName(nextDatasetName("tools-bootstrap"));
      setNotice({
        tone: "success",
        title: "Bootstrap dataset created",
        body: `${payload.rows_written} rows written to ${payload.dataset.name}.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Bootstrap failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsBootstrapping(false);
    }
  }


  async function handleCreateManualDataset() {
    setIsSavingManual(true);
    setNotice(null);
    try {
      const payload = await createManualDataset(manualDatasetName, manualContent);
      await reloadDatasets(false);
      setSelectedDataset(payload.dataset.name);
      await loadDatasetPreview(payload.dataset.name);
      setManualDatasetName(nextDatasetName("manual-dataset"));
      setNotice({
        tone: "success",
        title: "Manual dataset created",
        body: `${payload.dataset.name} is ready for preview and training.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Could not create manual dataset",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsSavingManual(false);
    }
  }


  async function handleAppendRows() {
    if (!selectedDataset) {
      return;
    }

    setIsAppendingRows(true);
    setNotice(null);
    try {
      await appendDatasetRows(selectedDataset, appendContent);
      await reloadDatasets(true);
      await loadDatasetPreview(selectedDataset);
      setNotice({
        tone: "success",
        title: "Rows appended",
        body: `Draft rows were appended to ${selectedDataset}.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Could not append rows",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsAppendingRows(false);
    }
  }


  async function handleValidateDataset(datasetName: string) {
    setNotice(null);
    try {
      const report = await validateDataset(datasetName);
      await reloadDatasets(true);
      if (datasetName === selectedDataset) {
        await loadDatasetPreview(datasetName);
      }
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


  async function handleDuplicateDataset(datasetName: string) {
    setNotice(null);
    try {
      const payload = await duplicateDataset(datasetName);
      await reloadDatasets(false);
      setSelectedDataset(payload.dataset.name);
      await loadDatasetPreview(payload.dataset.name);
      setNotice({
        tone: "success",
        title: "Dataset duplicated",
        body: `${payload.dataset.name} is ready as a separate asset.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Could not duplicate dataset",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    }
  }


  async function handleDeleteDataset(datasetName: string) {
    if (!window.confirm(`Delete ${datasetName}?`)) {
      return;
    }

    setNotice(null);
    try {
      await deleteDataset(datasetName);
      const nextSelectedDataset = datasetName === selectedDataset ? "" : selectedDataset;
      if (!nextSelectedDataset) {
        setSelectedDataset("");
      }
      await reloadDatasets(datasetName !== selectedDataset);
      setNotice({
        tone: "success",
        title: "Dataset deleted",
        body: `${datasetName} was removed from the library.`,
      });
    } catch (error) {
      setNotice({
        tone: "error",
        title: "Could not delete dataset",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    }
  }


  async function handleUseForTraining(datasetName: string) {
    setSelectedDataset(datasetName);
    await loadDatasetPreview(datasetName);
    setNotice({
      tone: "info",
      title: "Dataset selected for training",
      body: `${datasetName} is now the active training asset.`,
    });
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

  const selectedDatasetDetails = datasetDetails?.dataset ?? datasets.find((dataset) => dataset.name === selectedDataset) ?? null;
  const isRunning = status?.status === "running";
  const canStartTraining = Boolean(selectedDatasetDetails && selectedDatasetDetails.validation_status === "valid" && !isRunning && !isStarting);

  if (loadState === "loading") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <span className="eyebrow">Step 02</span>
            <h1>Dataset + Training</h1>
            <p>Load dataset assets and the current run state.</p>
          </div>
        </header>
        <div className="panel panel--soft empty-state">
          <h2>Loading workflow state</h2>
          <p>Fetching dataset assets and training progress from the new backend.</p>
        </div>
      </section>
    );
  }

  if (loadState === "error") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <span className="eyebrow">Step 02</span>
            <h1>Dataset + Training</h1>
            <p>Work with dataset assets first, then launch training from a validated file.</p>
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
          <span className="eyebrow">Step 02</span>
          <h1>Dataset + Training</h1>
          <p>Dataset is a standalone asset. Tools are only one way to bootstrap it before training.</p>
        </div>
        <div className="page-header__meta">
          <span className="pill">{datasets.length} assets</span>
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
                <span className="eyebrow">Create dataset</span>
                <h2>Choose the source</h2>
              </div>
            </div>

            <div className="dataset-create-grid">
              <section className="panel panel--soft dataset-source-card">
                <div className="section-heading section-heading--tight">
                  <div>
                    <span className="eyebrow">Source 01</span>
                    <h3>Import JSONL</h3>
                  </div>
                </div>
                <p>Bring in an already prepared dataset file. Import now validates the contract before saving.</p>
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
              </section>

              <section className="panel panel--soft dataset-source-card">
                <div className="section-heading section-heading--tight">
                  <div>
                    <span className="eyebrow">Source 02</span>
                    <h3>Bootstrap from tools</h3>
                  </div>
                </div>
                <p>Use the current tool registry only as a starting scaffold for a new dataset asset.</p>
                <label className="field field--wide">
                  <span>Dataset name</span>
                  <input
                    className="input"
                    type="text"
                    value={bootstrapDatasetName}
                    onChange={(event) => setBootstrapDatasetName(event.target.value)}
                  />
                </label>
                <button
                  className="button button--secondary"
                  disabled={isBootstrapping || !bootstrapDatasetName.trim()}
                  onClick={() => void handleBootstrap()}
                  type="button"
                >
                  {isBootstrapping ? "Bootstrapping..." : "Bootstrap from tools"}
                </button>
              </section>

              <section className="panel panel--soft dataset-source-card dataset-source-card--wide">
                <div className="section-heading section-heading--tight">
                  <div>
                    <span className="eyebrow">Source 03</span>
                    <h3>Manual examples / templates</h3>
                  </div>
                </div>
                <p>Paste one or more JSONL rows, or start from a simple template and shape the asset yourself.</p>
                <div className="dataset-template-actions">
                  <button className="button button--secondary" type="button" onClick={() => setManualContent(TOOL_CALL_TEMPLATE)}>
                    Tool call template
                  </button>
                  <button className="button button--secondary" type="button" onClick={() => setManualContent(FALLBACK_TEMPLATE)}>
                    Fallback template
                  </button>
                </div>
                <div className="tool-editor__grid">
                  <label className="field field--wide">
                    <span>Dataset name</span>
                    <input
                      className="input"
                      type="text"
                      value={manualDatasetName}
                      onChange={(event) => setManualDatasetName(event.target.value)}
                    />
                  </label>
                  <label className="field field--wide">
                    <span>JSONL rows</span>
                    <textarea
                      className="code-input dataset-code-input"
                      value={manualContent}
                      onChange={(event) => setManualContent(event.target.value)}
                      rows={12}
                      spellCheck={false}
                    />
                  </label>
                </div>
                <button
                  className="button button--secondary"
                  disabled={isSavingManual || !manualDatasetName.trim() || !manualContent.trim()}
                  onClick={() => void handleCreateManualDataset()}
                  type="button"
                >
                  {isSavingManual ? "Saving..." : "Create manual dataset"}
                </button>
              </section>
            </div>
          </section>

          <section className="panel dataset-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Dataset library</span>
                <h2>Manage dataset assets</h2>
              </div>
              <button className="button button--secondary" type="button" onClick={() => void reloadDatasets()}>
                Refresh list
              </button>
            </div>

            {datasets.length === 0 ? (
              <div className="empty-state empty-state--compact">
                <p>Create the first dataset asset from import, tools bootstrap, or manual examples.</p>
              </div>
            ) : (
              <div className="dataset-library-grid">
                {datasets.map((dataset) => (
                  <article
                    key={dataset.name}
                    className={`panel panel--soft dataset-card${dataset.name === selectedDataset ? " dataset-card--active" : ""}`}
                  >
                    <div className="dataset-card__header">
                      <div>
                        <h3>{dataset.name}</h3>
                        <p>{formatDatasetSource(dataset.source)}</p>
                      </div>
                      <span className={`status-chip status-chip--${dataset.validation_status}`}>
                        {dataset.validation_status}
                      </span>
                    </div>

                    <div className="dataset-card__stats">
                      <div>
                        <span>Rows</span>
                        <strong>{dataset.row_count}</strong>
                      </div>
                      <div>
                        <span>Issues</span>
                        <strong>{dataset.issue_count}</strong>
                      </div>
                      <div>
                        <span>Size</span>
                        <strong>{dataset.size_bytes} bytes</strong>
                      </div>
                    </div>

                    <div className="dataset-card__actions">
                      <button className="button button--secondary" type="button" onClick={() => void loadDatasetPreview(dataset.name)}>
                        Preview
                      </button>
                      <button className="button button--secondary" type="button" onClick={() => void handleValidateDataset(dataset.name)}>
                        Validate
                      </button>
                      <a className="button button--secondary" href={getDatasetDownloadUrl(dataset.name)}>
                        Export
                      </a>
                      <button className="button button--secondary" type="button" onClick={() => void handleDuplicateDataset(dataset.name)}>
                        Duplicate
                      </button>
                      <button className="button button--secondary" type="button" onClick={() => void handleDeleteDataset(dataset.name)}>
                        Delete
                      </button>
                      <button className="button button--primary" type="button" onClick={() => void handleUseForTraining(dataset.name)}>
                        Use for training
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="panel dataset-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Preview + validation</span>
                <h2>{selectedDatasetDetails ? selectedDatasetDetails.name : "Select a dataset"}</h2>
              </div>
            </div>

            {selectedDatasetDetails && datasetDetails ? (
              <div className="dataset-preview-stack">
                <div className="dataset-summary panel panel--soft">
                  <div>
                    <span>Source</span>
                    <strong>{formatDatasetSource(selectedDatasetDetails.source)}</strong>
                  </div>
                  <div>
                    <span>Rows</span>
                    <strong>{selectedDatasetDetails.row_count}</strong>
                  </div>
                  <div>
                    <span>Updated</span>
                    <strong>{new Date(selectedDatasetDetails.updated_at).toLocaleString()}</strong>
                  </div>
                  <div>
                    <span>Validation</span>
                    <strong>{datasetDetails.validation.status}</strong>
                  </div>
                </div>

                <div className="panel panel--soft dataset-validation-card">
                  <div className="section-heading section-heading--tight">
                    <div>
                      <span className="eyebrow">Validation</span>
                      <h3>Current report</h3>
                    </div>
                    <span className={`status-chip status-chip--${datasetDetails.validation.status}`}>
                      {datasetDetails.validation.status}
                    </span>
                  </div>
                  <p>
                    {datasetDetails.validation.issue_count === 0
                      ? `${datasetDetails.validation.row_count} rows passed the current dataset contract.`
                      : `${datasetDetails.validation.issue_count} issues found across ${datasetDetails.validation.row_count} rows.`}
                  </p>
                  {datasetDetails.validation.issues.length > 0 ? (
                    <ul className="dataset-issues-list">
                      {datasetDetails.validation.issues.map((issue) => (
                        <li key={`${issue.line_number}-${issue.message}`}>
                          <strong>Line {issue.line_number}</strong>
                          <span>{issue.message}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>

                <div className="panel panel--soft dataset-preview-card">
                  <div className="section-heading section-heading--tight">
                    <div>
                      <span className="eyebrow">Preview</span>
                      <h3>First rows</h3>
                    </div>
                  </div>
                  <div className="dataset-preview-lines">
                    {datasetDetails.preview_lines.map((line) => (
                      <article key={line.line_number} className="dataset-preview-line">
                        <span>Line {line.line_number}</span>
                        <pre>{line.raw}</pre>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="panel panel--soft dataset-preview-card">
                  <div className="section-heading section-heading--tight">
                    <div>
                      <span className="eyebrow">Append rows</span>
                      <h3>Add manual examples</h3>
                    </div>
                  </div>
                  <div className="dataset-template-actions">
                    <button className="button button--secondary" type="button" onClick={() => setAppendContent(TOOL_CALL_TEMPLATE)}>
                      Tool call template
                    </button>
                    <button className="button button--secondary" type="button" onClick={() => setAppendContent(FALLBACK_TEMPLATE)}>
                      Fallback template
                    </button>
                  </div>
                  <textarea
                    className="code-input dataset-code-input"
                    value={appendContent}
                    onChange={(event) => setAppendContent(event.target.value)}
                    rows={10}
                    spellCheck={false}
                  />
                  <button
                    className="button button--secondary"
                    disabled={isAppendingRows || !appendContent.trim()}
                    onClick={() => void handleAppendRows()}
                    type="button"
                  >
                    {isAppendingRows ? "Appending..." : "Append manual rows"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="empty-state empty-state--compact">
                <p>Preview a dataset asset from the library to inspect rows and validation.</p>
              </div>
            )}
          </section>

          <section className="panel training-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Training</span>
                <h2>Train from the selected asset</h2>
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
                {selectedDatasetDetails ? (
                  <>
                    <span className="pill">Using {selectedDatasetDetails.name}</span>
                    <span className={`status-chip status-chip--${selectedDatasetDetails.validation_status}`}>
                      {selectedDatasetDetails.validation_status}
                    </span>
                  </>
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
            {selectedDatasetDetails && selectedDatasetDetails.validation_status !== "valid" ? (
              <p className="page-note">Validate or fix the selected dataset before training.</p>
            ) : null}
          </section>
        </div>

        <TrainingProgress status={status} />
      </div>
    </section>
  );
}
