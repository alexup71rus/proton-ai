import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  FileInput,
  Group,
  Modal,
  NumberInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import {
  IconAlertCircle,
  IconDatabase,
  IconFlask,
  IconFolder,
  IconListDetails,
  IconPlayerPlay,
  IconSettings,
  IconUpload,
} from "@tabler/icons-react";

import {
  fetchModelArtifactStatus,
  importModelArtifacts,
  type ModelArtifactStatusResponse,
  type WorkspaceModel,
} from "./api";
import { AppShell } from "./components/AppShell";
import { DirectoryPickerModal } from "./components/DirectoryPickerModal";
import { DatasetTrainingRoute } from "./routes/DatasetTraining";
import { LogsRoute } from "./routes/Logs";
import { TestRoute } from "./routes/Test";
import { ToolsRoute } from "./routes/Tools";
import { compactWorkspacePath } from "./pathDisplay";
import {
  defaultWorkspaceModel,
  useWorkspaceState,
} from "./useWorkspaceState";


const navItems = [
  {
    to: "/",
    label: "Tools",
    description: "Registry",
    icon: <IconListDetails size={18} />,
  },
  {
    to: "/dataset-training",
    label: "Training",
    description: "Dataset",
    icon: <IconDatabase size={18} />,
  },
  {
    to: "/test",
    label: "Test",
    description: "Router run",
    icon: <IconPlayerPlay size={18} />,
  },
  {
    to: "/logs",
    label: "Logs",
    description: "Incidents",
    icon: <IconFlask size={18} />,
  },
];


type ModelDialog = "create" | "load" | null;
type RootPickerTarget = "create" | "load" | null;


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


type ArtifactLookupState = {
  key: string;
  state: "loading" | "ready" | "error";
  status: ModelArtifactStatusResponse | null;
  error: string | null;
};


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


function numberOrFallback(value: string | number, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}


function artifactLookupKey(target: Exclude<RootPickerTarget, null>, outputRootDir: string, artifactName: string): string {
  return `${target}:${outputRootDir.trim()}:${artifactName.trim()}`;
}


function getArtifactNameInputError(artifactName: string): string | null {
  const trimmed = artifactName.trim();
  if (!trimmed) {
    return "Artifact name is required.";
  }
  if (trimmed.includes("/") || trimmed.includes("\\")) {
    return "Use a file name, not a path.";
  }
  if (trimmed === "." || trimmed === "..") {
    return "Use a real file name.";
  }
  return null;
}


function getExistingArtifactPaths(status: ModelArtifactStatusResponse): string[] {
  return [
    status.model_exists ? status.model_path : null,
    status.tokenizer_exists ? status.tokenizer_path : null,
    status.vocab_exists ? status.vocab_path : null,
  ].filter((path): path is string => Boolean(path));
}


function getArtifactBlockingMessage(
  outputRootDir: string,
  artifactName: string,
  lookup: ArtifactLookupState | null,
): string | null {
  if (!outputRootDir.trim()) {
    return "Artifacts root is required.";
  }
  const nameError = getArtifactNameInputError(artifactName);
  if (nameError) {
    return nameError;
  }
  if (!lookup || lookup.state === "loading") {
    return "Checking artifact name...";
  }
  if (lookup.state === "error") {
    return lookup.error || "Could not check artifact name.";
  }
  if (lookup.status?.exists) {
    return `Artifact "${lookup.status.artifact_name}" already exists in ${compactWorkspacePath(lookup.status.output_root_dir)}. Choose another name or root.`;
  }
  return null;
}


function ArtifactStatusNotice({
  lookup,
  blockingMessage,
}: {
  lookup: ArtifactLookupState | null;
  blockingMessage: string | null;
}) {
  if (!blockingMessage) {
    return null;
  }
  if (lookup?.state === "loading" || blockingMessage === "Checking artifact name...") {
    return <Text size="sm" c="dimmed">Checking artifact name...</Text>;
  }

  const existingPaths = lookup?.status?.exists ? getExistingArtifactPaths(lookup.status) : [];

  return (
    <Alert color="red" icon={<IconAlertCircle size={18} />}>
      <Stack gap={4}>
        <Text size="sm">{blockingMessage}</Text>
        {existingPaths.length > 0 ? (
          <Text size="xs" c="dimmed">
            Existing files: {existingPaths.map((path) => compactWorkspacePath(path)).join(", ")}
          </Text>
        ) : null}
      </Stack>
    </Alert>
  );
}


type ArtifactRootInputProps = {
  value: string;
  currentRoot: string;
  onChange: (value: string) => void;
  onBrowse: () => void;
};


function ArtifactRootInput({ value, currentRoot, onChange, onBrowse }: ArtifactRootInputProps) {
  const presets = [
    { label: "data/", value: "data" },
    ...(currentRoot && currentRoot !== "data" ? [{ label: "current", value: currentRoot }] : []),
  ];

  return (
    <Stack gap={6}>
      <Group align="flex-end" wrap="nowrap">
        <TextInput
          label="Artifacts root"
          description="Folder for weights and tokenizer files."
          value={value}
          leftSection={<IconFolder size={16} />}
          onChange={(event) => onChange(event.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button variant="default" leftSection={<IconFolder size={16} />} onClick={onBrowse}>
          Browse
        </Button>
      </Group>
      <Group gap={6}>
        {presets.map((preset) => (
          <Button
            key={`${preset.label}-${preset.value}`}
            size="compact-xs"
            variant="light"
            onClick={() => onChange(preset.value)}
          >
            {preset.label}
          </Button>
        ))}
      </Group>
    </Stack>
  );
}


export function App() {
  const {
    selectedModel,
    trainingSettings,
    testSettings,
    workspaceLoadState,
    workspaceLoadError,
    persistWorkspace,
    applyTrainingSettings,
    applyTestSettings,
    handleTrainingResolved,
  } = useWorkspaceState();
  const [dialog, setDialog] = useState<ModelDialog>(null);
  const [createDraft, setCreateDraft] = useState<CreateModelDraft>(() => toCreateDraft(defaultWorkspaceModel()));
  const [loadDraft, setLoadDraft] = useState<LoadModelDraft>(() => toLoadDraft(defaultWorkspaceModel()));
  const [rootPickerTarget, setRootPickerTarget] = useState<RootPickerTarget>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [isImportingModel, setIsImportingModel] = useState(false);
  const [artifactLookup, setArtifactLookup] = useState<ArtifactLookupState | null>(null);

  const createArtifactKey = artifactLookupKey("create", createDraft.output_root_dir, createDraft.artifact_name);
  const loadArtifactKey = artifactLookupKey("load", loadDraft.output_root_dir, loadDraft.artifact_name);
  const createArtifactLookup = artifactLookup?.key === createArtifactKey ? artifactLookup : null;
  const loadArtifactLookup = artifactLookup?.key === loadArtifactKey ? artifactLookup : null;
  const createArtifactBlocker = getArtifactBlockingMessage(
    createDraft.output_root_dir,
    createDraft.artifact_name,
    createArtifactLookup,
  );
  const loadArtifactBlocker = getArtifactBlockingMessage(
    loadDraft.output_root_dir,
    loadDraft.artifact_name,
    loadArtifactLookup,
  );

  useEffect(() => {
    const target: Exclude<RootPickerTarget, null> | null = dialog === "create" || dialog === "load" ? dialog : null;
    if (!target) {
      setArtifactLookup(null);
      return;
    }

    const draft = target === "create" ? createDraft : loadDraft;
    const outputRootDir = draft.output_root_dir.trim();
    const artifactName = draft.artifact_name.trim();
    const key = artifactLookupKey(target, outputRootDir, artifactName);
    if (!outputRootDir || getArtifactNameInputError(artifactName)) {
      setArtifactLookup(null);
      return;
    }

    let cancelled = false;
    const timeout = window.setTimeout(() => {
      setArtifactLookup({ key, state: "loading", status: null, error: null });
      void fetchModelArtifactStatus(outputRootDir, artifactName)
        .then((status) => {
          if (!cancelled) {
            setArtifactLookup({ key, state: "ready", status, error: null });
          }
        })
        .catch((error) => {
          if (!cancelled) {
            setArtifactLookup({
              key,
              state: "error",
              status: null,
              error: error instanceof Error ? error.message : "Could not check artifact name.",
            });
          }
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [
    createDraft.artifact_name,
    createDraft.output_root_dir,
    dialog,
    loadDraft.artifact_name,
    loadDraft.output_root_dir,
  ]);

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

  async function applyCreateModel() {
    if (createArtifactBlocker) {
      setWorkspaceNotice(createArtifactBlocker);
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
      setWorkspaceNotice(error instanceof Error ? error.message : "Could not save model draft.");
    }
  }

  async function applyLoadedModel() {
    if (loadArtifactBlocker) {
      setWorkspaceNotice(loadArtifactBlocker);
      return;
    }
    if (!loadDraft.checkpointFile || !loadDraft.tokenizerFile) {
      setWorkspaceNotice("Choose checkpoint `.pt` and tokenizer `.model` files.");
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
      setWorkspaceNotice(error instanceof Error ? error.message : "Could not load model files.");
    } finally {
      setIsImportingModel(false);
    }
  }

  function applyPickedArtifactRoot(path: string) {
    setWorkspaceNotice(null);
    if (rootPickerTarget === "create") {
      setCreateDraft((current) => ({ ...current, output_root_dir: path }));
      return;
    }
    if (rootPickerTarget === "load") {
      setLoadDraft((current) => ({ ...current, output_root_dir: path }));
    }
  }

  const workspaceToolbar = (
    <Group gap="xs" wrap="nowrap">
      <div className="model-summary-pill">
        <Badge size="sm" variant={selectedModel.mode === "loaded" ? "filled" : "light"}>
          {selectedModel.mode === "loaded" ? "loaded" : "draft"}
        </Badge>
        <Text size="sm" fw={650} truncate maw={180}>
          {selectedModel.label}
        </Text>
      </div>
      <Button size="xs" variant="light" leftSection={<IconSettings size={15} />} onClick={openCreateDialog}>
        Configure
      </Button>
      <Button size="xs" variant="subtle" leftSection={<IconUpload size={15} />} onClick={openLoadDialog}>
        Import
      </Button>
    </Group>
  );

  const workspaceContent = workspaceLoadState === "loading" ? (
    <Stack gap="md">
      <Text c="dimmed">Loading workspace...</Text>
    </Stack>
  ) : workspaceLoadState === "error" ? (
    <Alert color="red" title="Workspace load failed" icon={<IconAlertCircle size={18} />}>
      {workspaceLoadError || "Unknown error."}
    </Alert>
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

      <Modal opened={workspaceLoadState === "ready" && dialog === "create"} onClose={() => setDialog(null)} title="Model draft" size="lg" centered>
        <Stack>
          <ArtifactRootInput
            value={createDraft.output_root_dir}
            currentRoot={selectedModel.output_root_dir}
            onChange={(output_root_dir) => {
              setWorkspaceNotice(null);
              setCreateDraft((current) => ({ ...current, output_root_dir }));
            }}
            onBrowse={() => setRootPickerTarget("create")}
          />

          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput
              label="Artifact name"
              error={getArtifactNameInputError(createDraft.artifact_name)}
              value={createDraft.artifact_name}
              onChange={(event) => {
                setWorkspaceNotice(null);
                setCreateDraft((current) => ({ ...current, artifact_name: event.currentTarget.value }));
              }}
            />
            <NumberInput
              label="Hidden size"
              min={8}
              step={8}
              value={createDraft.hidden_dim}
              onChange={(value) => setCreateDraft((current) => ({ ...current, hidden_dim: numberOrFallback(value, 64) }))}
            />
            <NumberInput
              label="Layers"
              min={1}
              value={createDraft.num_layers}
              onChange={(value) => setCreateDraft((current) => ({ ...current, num_layers: numberOrFallback(value, 1) }))}
            />
            <NumberInput
              label="Heads"
              min={1}
              value={createDraft.num_heads}
              onChange={(value) => setCreateDraft((current) => ({ ...current, num_heads: numberOrFallback(value, 1) }))}
            />
          </SimpleGrid>

          <ArtifactStatusNotice lookup={createArtifactLookup} blockingMessage={createArtifactBlocker} />

          {workspaceNotice ? (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>{workspaceNotice}</Alert>
          ) : null}

          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDialog(null)}>Cancel</Button>
            <Button disabled={Boolean(createArtifactBlocker)} onClick={() => void applyCreateModel()}>Save draft</Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={workspaceLoadState === "ready" && dialog === "load"} onClose={() => setDialog(null)} title="Load model files" size="lg" centered>
        <Stack>
          <ArtifactRootInput
            value={loadDraft.output_root_dir}
            currentRoot={selectedModel.output_root_dir}
            onChange={(output_root_dir) => {
              setWorkspaceNotice(null);
              setLoadDraft((current) => ({ ...current, output_root_dir }));
            }}
            onBrowse={() => setRootPickerTarget("load")}
          />
          <TextInput
            label="Artifact name"
            error={getArtifactNameInputError(loadDraft.artifact_name)}
            value={loadDraft.artifact_name}
            onChange={(event) => {
              setWorkspaceNotice(null);
              setLoadDraft((current) => ({ ...current, artifact_name: event.currentTarget.value }));
            }}
          />
          <FileInput
            label="Checkpoint file"
            accept=".pt"
            value={loadDraft.checkpointFile}
            onChange={(file) => setLoadDraft((current) => ({ ...current, checkpointFile: file }))}
          />
          <FileInput
            label="Tokenizer file"
            accept=".model"
            value={loadDraft.tokenizerFile}
            onChange={(file) => setLoadDraft((current) => ({ ...current, tokenizerFile: file }))}
          />
          <FileInput
            label="Tokenizer vocab"
            accept=".vocab"
            value={loadDraft.vocabFile}
            onChange={(file) => setLoadDraft((current) => ({ ...current, vocabFile: file }))}
            clearable
          />

          {workspaceNotice ? (
            <Alert color="red" icon={<IconAlertCircle size={18} />}>{workspaceNotice}</Alert>
          ) : null}

          <ArtifactStatusNotice lookup={loadArtifactLookup} blockingMessage={loadArtifactBlocker} />

          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDialog(null)}>Cancel</Button>
            <Button loading={isImportingModel} disabled={Boolean(loadArtifactBlocker)} onClick={() => void applyLoadedModel()}>
              Load selected files
            </Button>
          </Group>
        </Stack>
      </Modal>

      <DirectoryPickerModal
        opened={rootPickerTarget !== null}
        initialPath={rootPickerTarget === "load" ? loadDraft.output_root_dir : createDraft.output_root_dir}
        title="Choose artifacts root"
        onClose={() => setRootPickerTarget(null)}
        onSelect={applyPickedArtifactRoot}
      />
    </>
  );
}
