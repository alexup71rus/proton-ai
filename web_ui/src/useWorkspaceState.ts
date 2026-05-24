import { useEffect, useState } from "react";

import {
  fetchWorkspaceSettings,
  saveWorkspaceSettings,
  type TrainingStatus,
  type WorkspaceModel,
  type WorkspaceSettingsResponse,
  type WorkspaceTestSettings,
  type WorkspaceTrainingSettings,
} from "./api";


export type WorkspaceLoadState = "loading" | "ready" | "error";


export function defaultWorkspaceModel(): WorkspaceModel {
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


export function defaultTrainingSettings(): WorkspaceTrainingSettings {
  return {
    dataset_name: "routing.jsonl",
    epochs: 1,
    batch_size: 1,
  };
}


export function defaultTestSettings(): WorkspaceTestSettings {
  return {
    user_text: "сделай свет потеплее",
    answer_allowed: false,
    show_debug: false,
  };
}


type UseWorkspaceStateResult = {
  selectedModel: WorkspaceModel;
  trainingSettings: WorkspaceTrainingSettings;
  testSettings: WorkspaceTestSettings;
  workspaceLoadState: WorkspaceLoadState;
  workspaceLoadError: string | null;
  persistWorkspace: (
    nextModel: WorkspaceModel,
    nextTraining: WorkspaceTrainingSettings,
    nextTest: WorkspaceTestSettings,
  ) => Promise<void>;
  applyTrainingSettings: (nextTraining: WorkspaceTrainingSettings) => Promise<void>;
  applyTestSettings: (nextTest: WorkspaceTestSettings) => Promise<void>;
  handleTrainingResolved: (status: TrainingStatus) => void;
};


export function useWorkspaceState(): UseWorkspaceStateResult {
  const [selectedModel, setSelectedModel] = useState<WorkspaceModel>(() => defaultWorkspaceModel());
  const [trainingSettings, setTrainingSettings] = useState<WorkspaceTrainingSettings>(() => defaultTrainingSettings());
  const [testSettings, setTestSettings] = useState<WorkspaceTestSettings>(() => defaultTestSettings());
  const [workspaceLoadState, setWorkspaceLoadState] = useState<WorkspaceLoadState>("loading");
  const [workspaceLoadError, setWorkspaceLoadError] = useState<string | null>(null);

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

  async function persistWorkspace(
    nextModel: WorkspaceModel,
    nextTraining: WorkspaceTrainingSettings,
    nextTest: WorkspaceTestSettings,
  ) {
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

  return {
    selectedModel,
    trainingSettings,
    testSettings,
    workspaceLoadState,
    workspaceLoadError,
    persistWorkspace,
    applyTrainingSettings,
    applyTestSettings,
    handleTrainingResolved,
  };
}