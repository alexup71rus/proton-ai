import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  FileButton,
  Group,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconDownload, IconFolder, IconRefresh, IconRosetteDiscountCheck, IconUpload } from "@tabler/icons-react";

import {
  fetchDatasets,
  fetchTrainingStatus,
  getDatasetDownloadUrl,
  importDataset,
  startTraining,
  validateDataset,
  type DatasetSummary,
  type TrainingStatus,
  type WorkspaceModel,
  type WorkspaceTrainingSettings,
} from "../api";
import { DirectoryPickerModal } from "../components/DirectoryPickerModal";
import { TrainingProgress } from "../components/TrainingProgress";

type Notice = {
  tone: "green" | "red" | "blue";
  title: string;
  body?: string;
};


type DatasetTrainingRouteProps = {
  selectedModel: WorkspaceModel;
  trainingSettings: WorkspaceTrainingSettings;
  onTrainingSettingsChange: (next: WorkspaceTrainingSettings) => Promise<void>;
  onModelResolved: (status: TrainingStatus) => void;
};


const TRAINING_STATUS_POLL_MS = 1200 * 2;


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


function formatSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 12) : "pending";
}


function compactPath(path: string): string {
  const marker = "/proton-x/";
  const markerIndex = path.indexOf(marker);
  if (markerIndex >= 0) {
    return path.slice(markerIndex + marker.length);
  }
  return path;
}


function numberOrFallback(value: string | number, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}


function NoticeBanner({ notice }: { notice: Notice | null }) {
  if (!notice) {
    return null;
  }

  return (
    <Alert color={notice.tone} title={notice.title} icon={notice.tone === "red" ? <IconAlertCircle size={18} /> : undefined}>
      {notice.body}
    </Alert>
  );
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
  const [isImportingDataset, setIsImportingDataset] = useState(false);
  const [isSwitchingDatasetDir, setIsSwitchingDatasetDir] = useState(false);
  const [datasetPickerOpen, setDatasetPickerOpen] = useState(false);
  const [datasetDir, setDatasetDir] = useState("");
  const onModelResolvedRef = useRef(onModelResolved);

  const selectedDataset = trainingSettings.dataset_name;
  const datasetStoragePath = datasetDir || trainingSettings.dataset_dir || "data/train/routing";
  const selectedDatasetDetails = datasets.find((dataset) => dataset.name === selectedDataset) ?? null;
  const isRunning = status?.status === "running";
  const canStartTraining = Boolean(
    selectedDataset.trim()
    && selectedModel.output_root_dir.trim()
    && selectedModel.artifact_name.trim()
    && !isRunning
    && !isStarting
  );

  async function persistTrainingSettings(next: WorkspaceTrainingSettings) {
    try {
      await onTrainingSettingsChange(next);
    } catch (error) {
      setNotice({
        tone: "red",
        title: "Workspace settings failed",
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
      setDatasetDir(datasetsPayload.dataset_dir);
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
        tone: "red",
        title: "Could not load training state",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
      setLoadState("error");
    }
  }

  useEffect(() => {
    onModelResolvedRef.current = onModelResolved;
  }, [onModelResolved]);

  useEffect(() => {
    void loadScreen();
  }, []);

  useEffect(() => {
    if (status?.status !== "running") {
      return undefined;
    }

    let cancelled = false;
    let timeout: number | undefined;

    async function pollTrainingStatus() {
      let shouldContinue = true;
      try {
        const payload = await fetchTrainingStatus();
        if (cancelled) {
          return;
        }
        setStatus(payload);
        if (payload.model_path && payload.tokenizer_path) {
          onModelResolvedRef.current(payload);
        }
        shouldContinue = payload.status === "running";
      } catch {
        shouldContinue = true;
      } finally {
        if (!cancelled && shouldContinue) {
          timeout = window.setTimeout(pollTrainingStatus, TRAINING_STATUS_POLL_MS);
        }
      }
    }

    timeout = window.setTimeout(pollTrainingStatus, TRAINING_STATUS_POLL_MS);

    return () => {
      cancelled = true;
      if (timeout !== undefined) {
        window.clearTimeout(timeout);
      }
    };
  }, [status?.status]);

  async function reloadDatasets(preserveSelection = true) {
    const payload = await fetchDatasets();
    setDatasets(payload.datasets);
    setDatasetDir(payload.dataset_dir);
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

  async function handleDatasetDirSelect(path: string) {
    if (isRunning) {
      return;
    }

    setIsSwitchingDatasetDir(true);
    setNotice(null);
    const nextSettings = {
      ...trainingSettings,
      dataset_dir: path,
      dataset_name: "",
    };

    try {
      await onTrainingSettingsChange(nextSettings);
      const payload = await fetchDatasets();
      const nextSelectedDataset = payload.datasets[0]?.name ?? "";
      setDatasets(payload.datasets);
      setDatasetDir(payload.dataset_dir);
      if (nextSelectedDataset) {
        await onTrainingSettingsChange({
          ...nextSettings,
          dataset_name: nextSelectedDataset,
        });
      }
      setNotice({
        tone: "blue",
        title: "Dataset storage updated",
        body: compactPath(payload.dataset_dir),
      });
    } catch (error) {
      setNotice({
        tone: "red",
        title: "Dataset storage failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsSwitchingDatasetDir(false);
    }
  }

  async function handleValidateDataset(datasetName: string) {
    if (!datasetName) {
      return;
    }
    setNotice(null);
    try {
      const report = await validateDataset(datasetName);
      await reloadDatasets(true);
      setNotice({
        tone: report.status === "valid" ? "green" : "red",
        title: report.status === "valid" ? "Dataset is valid" : "Dataset has issues",
        body: report.status === "valid"
          ? `${datasetName}: ${report.row_count} rows.`
          : `${datasetName}: ${report.issue_count} issues.`,
      });
    } catch (error) {
      setNotice({
        tone: "red",
        title: "Validation failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    }
  }

  async function handleImportDataset(file: File | null) {
    if (!file) {
      return;
    }

    setIsImportingDataset(true);
    setNotice(null);
    try {
      const payload = await importDataset(file);
      const datasetsPayload = await fetchDatasets();
      setDatasets(datasetsPayload.datasets);
      setDatasetDir(datasetsPayload.dataset_dir);
      await onTrainingSettingsChange({
        ...trainingSettings,
        dataset_name: payload.dataset.name,
      });
      setNotice({
        tone: "green",
        title: "Dataset imported",
        body: `${payload.dataset.name}: ${payload.dataset.row_count} rows.`,
      });
    } catch (error) {
      setNotice({
        tone: "red",
        title: "Dataset import failed",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsImportingDataset(false);
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
        epochs: trainingSettings.epochs,
        batch_size: trainingSettings.batch_size,
        learning_rate: trainingSettings.learning_rate,
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
        tone: "green",
        title: "Training started",
        body: selectedDataset,
      });
    } catch (error) {
      setNotice({
        tone: "red",
        title: "Training could not start",
        body: error instanceof Error ? error.message : "Unknown error.",
      });
    } finally {
      setIsStarting(false);
    }
  }

  function patchTrainingSettings(patch: Partial<WorkspaceTrainingSettings>) {
    void persistTrainingSettings({
      ...trainingSettings,
      ...patch,
    });
  }

  if (loadState === "loading") {
    return (
      <Card>
        <Text c="dimmed">Loading datasets and training state...</Text>
      </Card>
    );
  }

  if (loadState === "error") {
    return (
      <Stack>
        <NoticeBanner notice={notice} />
        <Button leftSection={<IconRefresh size={16} />} onClick={() => void loadScreen()}>
          Retry
        </Button>
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Training</Title>
          <Text c="dimmed" size="sm">
            {datasets.length} dataset files
          </Text>
        </div>
        <Badge color={isRunning ? "blue" : "gray"}>{isRunning ? "running" : "idle"}</Badge>
      </Group>

      <NoticeBanner notice={notice} />

      <div className="route-grid route-grid--training">
        <Stack>
          <Card>
            <Stack>
              <Group justify="space-between">
                <div>
                  <Title order={3}>Dataset</Title>
                  <Text size="sm" c="dimmed">Storage: {compactPath(datasetStoragePath)}</Text>
                </div>
                <Group gap="xs">
                  <Button
                    variant="default"
                    leftSection={<IconFolder size={16} />}
                    loading={isSwitchingDatasetDir}
                    disabled={isRunning}
                    onClick={() => setDatasetPickerOpen(true)}
                  >
                    Browse
                  </Button>
                  <FileButton onChange={(file) => void handleImportDataset(file)} accept=".jsonl,application/json,text/plain">
                    {(props) => (
                      <Button
                        {...props}
                        variant="light"
                        leftSection={<IconUpload size={16} />}
                        loading={isImportingDataset}
                        disabled={isRunning}
                      >
                        Import
                      </Button>
                    )}
                  </FileButton>
                  <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={() => void reloadDatasets()}>
                    Refresh
                  </Button>
                </Group>
              </Group>

              <Select
                label="Dataset file"
                value={selectedDataset || null}
                data={datasets.map((dataset) => ({ value: dataset.name, label: dataset.name }))}
                disabled={isRunning || datasets.length === 0}
                onChange={(value) => patchTrainingSettings({ dataset_name: value ?? "" })}
              />

              {selectedDatasetDetails ? (
                <SimpleGrid cols={{ base: 2, md: 3 }}>
                  <Card bg="dark.7">
                    <Text size="xs" c="dimmed">Rows</Text>
                    <Text fw={700}>{selectedDatasetDetails.row_count}</Text>
                  </Card>
                  <Card bg="dark.7">
                    <Text size="xs" c="dimmed">Source</Text>
                    <Text fw={700}>{formatDatasetSource(selectedDatasetDetails.source)}</Text>
                  </Card>
                  <Card bg="dark.7">
                    <Text size="xs" c="dimmed">Validation</Text>
                    <Text fw={700}>{selectedDatasetDetails.validation_status}</Text>
                  </Card>
                  <Card bg="dark.7">
                    <Text size="xs" c="dimmed">Issues</Text>
                    <Text fw={700}>{selectedDatasetDetails.issue_count}</Text>
                  </Card>
                  <Card bg="dark.7">
                    <Text size="xs" c="dimmed">SHA1</Text>
                    <Text fw={700}>{formatSha(selectedDatasetDetails.sha1)}</Text>
                  </Card>
                </SimpleGrid>
              ) : (
                <Text c="dimmed" size="sm">No dataset selected.</Text>
              )}

              <Group justify="flex-end">
                <Button
                  variant="default"
                  leftSection={<IconRosetteDiscountCheck size={16} />}
                  disabled={!selectedDataset}
                  onClick={() => void handleValidateDataset(selectedDataset)}
                >
                  Validate
                </Button>
                {selectedDatasetDetails ? (
                  <Button
                    component="a"
                    variant="default"
                    href={getDatasetDownloadUrl(selectedDatasetDetails.name)}
                    leftSection={<IconDownload size={16} />}
                  >
                    Download
                  </Button>
                ) : null}
              </Group>
            </Stack>
          </Card>

          <Card>
            <Stack>
              <Title order={3}>Training config</Title>
              <SimpleGrid cols={{ base: 1, sm: 3 }}>
                <NumberInput
                  label="Epochs"
                  min={1}
                  value={trainingSettings.epochs}
                  disabled={isRunning}
                  onChange={(value) => patchTrainingSettings({ epochs: numberOrFallback(value, 1) })}
                />
                <NumberInput
                  label="Batch size"
                  min={1}
                  value={trainingSettings.batch_size}
                  disabled={isRunning}
                  onChange={(value) => patchTrainingSettings({ batch_size: numberOrFallback(value, 1) })}
                />
                <NumberInput
                  label="Learning rate"
                  min={0}
                  decimalScale={6}
                  step={0.0001}
                  value={trainingSettings.learning_rate}
                  disabled={isRunning}
                  onChange={(value) => patchTrainingSettings({ learning_rate: numberOrFallback(value, 0.001) })}
                />
              </SimpleGrid>

              <SimpleGrid cols={{ base: 1, md: 3 }}>
                <Card bg="dark.7">
                  <Text size="xs" c="dimmed">Artifact</Text>
                  <Text fw={700}>{selectedModel.artifact_name}</Text>
                </Card>
                <Card bg="dark.7">
                  <Text size="xs" c="dimmed">Root</Text>
                  <Text fw={700}>{compactPath(selectedModel.output_root_dir)}</Text>
                </Card>
                <Card bg="dark.7">
                  <Text size="xs" c="dimmed">Shape</Text>
                  <Text fw={700}>{selectedModel.hidden_dim}/{selectedModel.num_layers}/{selectedModel.num_heads}</Text>
                </Card>
              </SimpleGrid>

              <Group justify="flex-end">
                <Button disabled={!canStartTraining} loading={isStarting} onClick={() => void handleStartTraining()}>
                  {isRunning ? "Training in progress" : "Start training"}
                </Button>
              </Group>
            </Stack>
          </Card>
        </Stack>

        <TrainingProgress status={status} />
      </div>

      <DirectoryPickerModal
        opened={datasetPickerOpen}
        initialPath={datasetStoragePath}
        title="Choose dataset storage"
        onClose={() => setDatasetPickerOpen(false)}
        onSelect={(path) => void handleDatasetDirSelect(path)}
      />
    </Stack>
  );
}
