import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import {
  fetchWorkspaceSettings,
  importModelArtifacts,
  saveWorkspaceSettings,
  type TrainingStatus,
  type WorkspaceModel,
  type WorkspaceSettingsResponse,
  type WorkspaceTestSettings,
  type WorkspaceTrainingSettings,
} from "./api";
import { AppShell } from "./components/AppShell";
import { DatasetTrainingRoute } from "./routes/DatasetTraining";
import { LogsRoute } from "./routes/Logs";
import { TestRoute } from "./routes/Test";
import { ToolsRoute } from "./routes/Tools";


const navItems = [
  {
    to: "/",
    label: "Tools",
    step: "01",
    description: "Define the registry and keep the source of truth clean.",
  },
  {
    to: "/dataset-training",
    label: "Dataset + Training",
    step: "02",
    description: "Pick a dataset, then train or fine-tune the active model.",
  },
  {
    to: "/test",
    label: "Test",
    step: "03",
    description: "Run requests against the currently selected model.",
  },
  {
    to: "/logs",
    label: "Logs",
    step: "04",
    description: "Turn failures into the next improvement loop.",
  },
];


type ModelDialog = "create" | "load" | null;


type CreateModelDraft = {
  output_root_dir: string;
  artifact_name: string;
  hidden_dim: number;
  num_layers: number;
  num_heads: number;
};


type LoadModelDraft = {
  output_root_dir: string;
  artifact_name: string;
  checkpointFile: File | null;
  tokenizerFile: File | null;
  vocabFile: File | null;
};


function defaultWorkspaceModel(): WorkspaceModel {
  return {
    mode: "new",
    label: "tiny_router_v1",
    model_name: "tiny-router",
    tokenizer_name: "sentencepiece-bpe",
    output_root_dir: "data",
    artifact_name: "tiny_router_v1",
    model_path: null,
    tokenizer_path: null,
    hidden_dim: 64,
    num_layers: 2,
    num_heads: 4,
  };
}


function defaultTrainingSettings(): WorkspaceTrainingSettings {
  return {
    dataset_name: "routing.jsonl",
    epochs: 1,
    batch_size: 1,
  };
}


function defaultTestSettings(): WorkspaceTestSettings {
  return {
    user_text: "сделай свет потеплее",
    answer_allowed: false,
    show_debug: false,
  };
}


function toCreateDraft(model: WorkspaceModel): CreateModelDraft {
  return {
    output_root_dir: model.output_root_dir,
    artifact_name: model.artifact_name,
    hidden_dim: model.hidden_dim,
    num_layers: model.num_layers,
    num_heads: model.num_heads,
  };
}


function toLoadDraft(model: WorkspaceModel): LoadModelDraft {
  return {
    output_root_dir: model.output_root_dir,
    artifact_name: model.artifact_name,
    checkpointFile: null,
    tokenizerFile: null,
    vocabFile: null,
  };
}


export function App() {
  const [selectedModel, setSelectedModel] = useState<WorkspaceModel>(() => defaultWorkspaceModel());
  const [trainingSettings, setTrainingSettings] = useState<WorkspaceTrainingSettings>(() => defaultTrainingSettings());
  const [testSettings, setTestSettings] = useState<WorkspaceTestSettings>(() => defaultTestSettings());
  const [workspaceLoadState, setWorkspaceLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [workspaceLoadError, setWorkspaceLoadError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<ModelDialog>(null);
  const [createDraft, setCreateDraft] = useState<CreateModelDraft>(() => toCreateDraft(defaultWorkspaceModel()));
  const [loadDraft, setLoadDraft] = useState<LoadModelDraft>(() => toLoadDraft(defaultWorkspaceModel()));
  const [workspaceNotice, setWorkspaceNotice] = useState<{ tone: "error" | "info"; message: string } | null>(null);
  const [isImportingModel, setIsImportingModel] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace() {
      try {
        const payload = await fetchWorkspaceSettings();
        if (cancelled) {
          return;
        }
        applyWorkspacePayload(payload);
        setWorkspaceLoadError(null);
        setWorkspaceLoadState("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }
        setWorkspaceLoadError(error instanceof Error ? error.message : "Could not load workspace settings.");
        setWorkspaceLoadState("error");
      }
    }

    void loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, []);

  function applyWorkspacePayload(payload: WorkspaceSettingsResponse) {
    setSelectedModel(payload.selected_model);
    setTrainingSettings(payload.training);
    setTestSettings(payload.test);
  }

  async function persistWorkspace(nextModel: WorkspaceModel, nextTraining: WorkspaceTrainingSettings, nextTest: WorkspaceTestSettings) {
    const payload = await saveWorkspaceSettings({
      selected_model: nextModel,
      training: nextTraining,
      test: nextTest,
    });
    applyWorkspacePayload(payload);
  }

  async function applyTrainingSettings(nextTraining: WorkspaceTrainingSettings) {
    await persistWorkspace(selectedModel, nextTraining, testSettings);
  }

  async function applyTestSettings(nextTest: WorkspaceTestSettings) {
    await persistWorkspace(selectedModel, trainingSettings, nextTest);
  }

  function openCreateDialog() {
    setCreateDraft(toCreateDraft(selectedModel));
    setWorkspaceNotice(null);
    setDialog("create");
  }

  function openLoadDialog() {
    setLoadDraft(toLoadDraft(selectedModel));
    setWorkspaceNotice(null);
    setDialog("load");
  }

  function closeDialog() {
    setDialog(null);
  }

  async function applyCreateModel() {
    if (!createDraft.output_root_dir.trim() || !createDraft.artifact_name.trim()) {
      setWorkspaceNotice({ tone: "error", message: "Fill the save root and artifact name before creating the model draft." });
      return;
    }

    try {
      await persistWorkspace(
        {
          mode: "new",
          label: createDraft.artifact_name,
          model_name: "tiny-router",
          tokenizer_name: "sentencepiece-bpe",
          output_root_dir: createDraft.output_root_dir,
          artifact_name: createDraft.artifact_name,
          model_path: null,
          tokenizer_path: null,
          hidden_dim: createDraft.hidden_dim,
          num_layers: createDraft.num_layers,
          num_heads: createDraft.num_heads,
        },
        trainingSettings,
        testSettings,
      );
      setWorkspaceNotice(null);
      setDialog(null);
    } catch (error) {
      setWorkspaceNotice({ tone: "error", message: error instanceof Error ? error.message : "Could not save model." });
    }
  }

  async function applyLoadedModel() {
    if (!loadDraft.checkpointFile || !loadDraft.tokenizerFile) {
      setWorkspaceNotice({ tone: "error", message: "Choose checkpoint and tokenizer files before loading the model." });
      return;
    }

    setIsImportingModel(true);
    setWorkspaceNotice(null);
    try {
      const payload = await importModelArtifacts({
        checkpointFile: loadDraft.checkpointFile,
        tokenizerFile: loadDraft.tokenizerFile,
        vocabFile: loadDraft.vocabFile,
        outputRootDir: loadDraft.output_root_dir,
        artifactName: loadDraft.artifact_name,
      });
      await persistWorkspace(
        {
          ...selectedModel,
          mode: "loaded",
          label: payload.artifact_name,
          output_root_dir: payload.output_root_dir,
          artifact_name: payload.artifact_name,
          model_path: payload.model_path,
          tokenizer_path: payload.tokenizer_path,
        },
        trainingSettings,
        testSettings,
      );
      setWorkspaceNotice(null);
      setDialog(null);
    } catch (error) {
      setWorkspaceNotice({ tone: "error", message: error instanceof Error ? error.message : "Model import failed." });
    } finally {
      setIsImportingModel(false);
    }
  }

  function handleTrainingResolved(status: TrainingStatus) {
    if (!status.model_path || !status.tokenizer_path) {
      return;
    }

    setSelectedModel((current) => ({
      ...current,
      mode: "loaded",
      label: status.artifact_name || current.label,
      model_name: status.model_name || current.model_name,
      tokenizer_name: status.tokenizer_name || current.tokenizer_name,
      output_root_dir: status.output_root_dir || current.output_root_dir,
      artifact_name: status.artifact_name || current.artifact_name,
      model_path: status.model_path,
      tokenizer_path: status.tokenizer_path,
    }));
  }

  const workspaceToolbar = (
    <section className="workspace-toolbar panel">
      <div className="workspace-toolbar__main">
        <div className="workspace-toolbar__title">
          <strong>{selectedModel.label}</strong>
        </div>

        <div className="workspace-toolbar__actions">
          <button className="button button--primary" type="button" onClick={openCreateDialog}>
            Create model
          </button>
          <button className="button button--secondary" type="button" onClick={openLoadDialog}>
            Load model
          </button>
        </div>
      </div>
    </section>
  );

  const workspaceContent = workspaceLoadState === "loading" ? (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>Workspace</h1>
          <p>Loading backend workspace settings.</p>
        </div>
      </header>
      <section className="panel empty-state">
        <h2>Loading workspace state</h2>
        <p>Selected model, training defaults and test settings are loaded from the backend.</p>
      </section>
    </section>
  ) : workspaceLoadState === "error" ? (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>Workspace</h1>
          <p>Backend workspace settings could not be loaded.</p>
        </div>
      </header>
      <div className="feedback feedback--error">
        <strong>Workspace load failed</strong>
        <p>{workspaceLoadError || "Unknown error."}</p>
      </div>
    </section>
  ) : (
    <Routes>
      <Route path="/" element={<ToolsRoute />} />
      <Route
        path="/dataset-training"
        element={
          <DatasetTrainingRoute
            selectedModel={selectedModel}
            trainingSettings={trainingSettings}
            onTrainingSettingsChange={applyTrainingSettings}
            onModelResolved={handleTrainingResolved}
          />
        }
      />
      <Route
        path="/test"
        element={<TestRoute selectedModel={selectedModel} testSettings={testSettings} onTestSettingsChange={applyTestSettings} />}
      />
      <Route path="/logs" element={<LogsRoute />} />
      <Route path="/Tools" element={<Navigate to="/" replace />} />
      <Route path="/Dataset_Training" element={<Navigate to="/dataset-training" replace />} />
      <Route path="/Test" element={<Navigate to="/test" replace />} />
      <Route path="/Logs" element={<Navigate to="/logs" replace />} />
    </Routes>
  );

  return (
    <>
      <AppShell navItems={navItems} workspaceToolbar={workspaceLoadState === "ready" ? workspaceToolbar : undefined}>
        {workspaceContent}
      </AppShell>

      {workspaceLoadState === "ready" && dialog === "create" ? (
        <div className="modal-backdrop" role="presentation" onClick={closeDialog}>
          <div className="modal-panel panel" role="dialog" aria-modal="true" aria-label="Create model" onClick={(event) => event.stopPropagation()}>
            <div className="section-heading section-heading--tight">
              <div>
                <span className="eyebrow">Model</span>
                <h2>Create model</h2>
              </div>
            </div>

            <div className="tool-editor__grid">
              <label className="field field--wide">
                <span>Artifacts root</span>
                <input className="input" type="text" value={createDraft.output_root_dir} onChange={(event) => setCreateDraft((current) => ({ ...current, output_root_dir: event.target.value }))} />
              </label>

              <label className="field field--wide">
                <span>Artifact name</span>
                <input className="input" type="text" value={createDraft.artifact_name} onChange={(event) => setCreateDraft((current) => ({ ...current, artifact_name: event.target.value }))} />
              </label>

              <label className="field">
                <span>Hidden size</span>
                <input className="input" type="number" min={8} step={8} value={createDraft.hidden_dim} onChange={(event) => setCreateDraft((current) => ({ ...current, hidden_dim: Number(event.target.value) || 64 }))} />
              </label>

              <label className="field">
                <span>Layers</span>
                <input className="input" type="number" min={1} value={createDraft.num_layers} onChange={(event) => setCreateDraft((current) => ({ ...current, num_layers: Number(event.target.value) || 1 }))} />
              </label>

              <label className="field">
                <span>Heads</span>
                <input className="input" type="number" min={1} value={createDraft.num_heads} onChange={(event) => setCreateDraft((current) => ({ ...current, num_heads: Number(event.target.value) || 1 }))} />
              </label>
            </div>

            {workspaceNotice?.tone === "error" ? (
              <div className="feedback feedback--error">
                <strong>Could not save model</strong>
                <p>{workspaceNotice.message}</p>
              </div>
            ) : null}

            <p className="page-note">This saves the active model draft. Actual checkpoint and tokenizer files will be written by the next training run.</p>

            <div className="modal-panel__actions">
              <button className="button button--secondary" type="button" onClick={closeDialog}>Cancel</button>
              <button className="button button--primary" type="button" onClick={() => void applyCreateModel()}>Save draft</button>
            </div>
          </div>
        </div>
      ) : null}

      {workspaceLoadState === "ready" && dialog === "load" ? (
        <div className="modal-backdrop" role="presentation" onClick={closeDialog}>
          <div className="modal-panel panel" role="dialog" aria-modal="true" aria-label="Load model" onClick={(event) => event.stopPropagation()}>
            <div className="section-heading section-heading--tight">
              <div>
                <span className="eyebrow">Model</span>
                <h2>Load model</h2>
              </div>
            </div>

            <div className="tool-editor__grid">
              <label className="field field--wide">
                <span>Artifacts root</span>
                <input className="input" type="text" value={loadDraft.output_root_dir} onChange={(event) => setLoadDraft((current) => ({ ...current, output_root_dir: event.target.value }))} />
              </label>

              <label className="field field--wide">
                <span>Artifact name</span>
                <input className="input" type="text" value={loadDraft.artifact_name} onChange={(event) => setLoadDraft((current) => ({ ...current, artifact_name: event.target.value }))} />
              </label>

              <label className="field field--wide">
                <span>Checkpoint file</span>
                <input className="input" type="file" accept=".pt" onChange={(event) => setLoadDraft((current) => ({ ...current, checkpointFile: event.target.files?.[0] ?? null }))} />
              </label>

              <label className="field field--wide">
                <span>Tokenizer file</span>
                <input className="input" type="file" accept=".model" onChange={(event) => setLoadDraft((current) => ({ ...current, tokenizerFile: event.target.files?.[0] ?? null }))} />
              </label>

              <label className="field field--wide">
                <span>Tokenizer vocab (optional)</span>
                <input className="input" type="file" accept=".vocab" onChange={(event) => setLoadDraft((current) => ({ ...current, vocabFile: event.target.files?.[0] ?? null }))} />
              </label>
            </div>

            {workspaceNotice?.tone === "error" ? (
              <div className="feedback feedback--error">
                <strong>Could not load model</strong>
                <p>{workspaceNotice.message}</p>
              </div>
            ) : null}

            <div className="modal-panel__actions">
              <button className="button button--secondary" type="button" onClick={closeDialog}>Cancel</button>
              <button className="button button--primary" type="button" disabled={isImportingModel} onClick={() => void applyLoadedModel()}>
                {isImportingModel ? "Loading..." : "Load selected files"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
