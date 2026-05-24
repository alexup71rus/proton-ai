export interface ToolDefinition {
  name: string;
  description: string;
  tags: string[];
  arguments_schema: Record<string, unknown>;
  executor_path: string;
}


export interface ToolsSource {
  name: string;
  path: string;
}


export interface ToolsResponse {
  tools: ToolDefinition[];
  source: ToolsSource;
}


export interface ToolsValidationResponse {
  valid: boolean;
  tool_count: number;
}


export interface DatasetSummary {
  name: string;
  size_bytes: number;
  updated_at: string;
  sha1: string;
  row_count: number;
  validation_status: "valid" | "invalid";
  issue_count: number;
  source: "imported" | "tools_bootstrap" | "manual" | "logs_draft";
}


export interface DatasetsResponse {
  datasets: DatasetSummary[];
}


export interface DatasetValidationIssue {
  line_number: number;
  message: string;
}


export interface DatasetValidationReport {
  status: "valid" | "invalid";
  row_count: number;
  issue_count: number;
  issues: DatasetValidationIssue[];
}


export interface DatasetPreviewLine {
  line_number: number;
  raw: string;
}


export interface DatasetDetailResponse {
  dataset: DatasetSummary;
  preview_lines: DatasetPreviewLine[];
  validation: DatasetValidationReport;
}


export interface DatasetBootstrapResponse {
  bootstrapped: boolean;
  rows_written: number;
  dataset: DatasetSummary;
}


export interface DatasetMutationResponse {
  saved: boolean;
  dataset: DatasetSummary;
}


export interface DatasetDuplicateResponse {
  duplicated: boolean;
  dataset: DatasetSummary;
}


export interface DatasetDeleteResponse {
  deleted: boolean;
  name: string;
}


export interface LogsExportResponse {
  exported: boolean;
  rows_written: number;
  dataset: DatasetSummary;
}


export interface WorkspaceModel {
  mode: "new" | "loaded";
  label: string;
  model_name: string;
  tokenizer_name: string;
  output_root_dir: string;
  artifact_name: string;
  model_path: string | null;
  tokenizer_path: string | null;
  hidden_dim: number;
  num_layers: number;
  num_heads: number;
}


export interface WorkspaceTrainingSettings {
  dataset_name: string;
  epochs: number;
  batch_size: number;
}


export interface WorkspaceTestSettings {
  user_text: string;
  answer_allowed: boolean;
  show_debug: boolean;
}


export interface WorkspaceSettingsPayload {
  selected_model: WorkspaceModel;
  training: WorkspaceTrainingSettings;
  test: WorkspaceTestSettings;
}


export interface WorkspaceSettingsResponse extends WorkspaceSettingsPayload {
  storage_path: string;
}


export interface TrainingStatus {
  status: string;
  current_epoch: number;
  total_epochs: number;
  current_step: number;
  total_steps: number;
  loss: number | null;
  loss_history: number[];
  metrics: Record<string, number>;
  error: string | null;
  batch_size: number;
  model_name: string;
  tokenizer_name: string;
  output_root_dir: string | null;
  artifact_name: string;
  checkpoint_path: string | null;
  model_path: string | null;
  tokenizer_path: string | null;
  dataset_path: string | null;
  dataset_sha1: string | null;
  dataset_row_count: number;
  eval_total: number;
  eval_valid: number;
  eval_exact: number;
  eval_positive_total: number;
  eval_positive_exact: number;
  eval_fallback_total: number;
  eval_fallback_exact: number;
}


export interface TrainingStartPayload {
  dataset_name: string;
  epochs: number;
  batch_size: number;
  model_name: string;
  tokenizer_name: string;
  output_root_dir: string;
  artifact_name: string;
  resume_model_path: string | null;
  resume_tokenizer_path: string | null;
  hidden_dim: number;
  num_layers: number;
  num_heads: number;
}


export interface TestRunPayload {
  user_text: string;
  answer_allowed?: boolean;
  model_path?: string | null;
  tokenizer_path?: string | null;
}


export interface ModelImportResponse {
  imported: boolean;
  output_root_dir: string;
  artifact_name: string;
  model_path: string;
  tokenizer_path: string;
}


export interface TestResponse {
  result: {
    status: string;
    tool_name: string | null;
    arguments: Record<string, unknown> | null;
    response: string | null;
    execution: {
      status: string;
      tool_name: string | null;
      output: unknown | null;
      error: string | null;
    } | null;
  };
  debug: {
    candidate_tools: string[];
    serialized_prompt: string;
    raw_model_output: string;
    repaired_output: string | null;
    validator_result: Record<string, unknown>;
    confidence: string;
    final_action: string;
  };
}


export interface LogRow {
  user: string;
  candidates: string[];
  raw_output_summary: string;
  raw_output: string;
  error: string;
  result: string;
}


export interface LogsResponse {
  rows: LogRow[];
}


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = "Request failed.";
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload?.detail)) {
        message = payload.detail.join("\n");
      } else if (typeof payload?.message === "string") {
        message = payload.message;
      }
    } catch {
      const text = await response.text();
      if (text) {
        message = text;
      }
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}


export async function fetchTools(): Promise<ToolsResponse> {
  return request<ToolsResponse>("/api/tools");
}


export async function fetchWorkspaceSettings(): Promise<WorkspaceSettingsResponse> {
  return request<WorkspaceSettingsResponse>("/api/workspace");
}


export async function saveWorkspaceSettings(payload: WorkspaceSettingsPayload): Promise<WorkspaceSettingsResponse> {
  return request<WorkspaceSettingsResponse>("/api/workspace", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}


export async function saveTools(tools: ToolDefinition[]): Promise<ToolsResponse & { saved: boolean }> {
  return request<ToolsResponse & { saved: boolean }>("/api/tools", {
    method: "PUT",
    body: JSON.stringify({ tools }),
  });
}


export async function validateTools(tools: ToolDefinition[]): Promise<ToolsValidationResponse> {
  return request<ToolsValidationResponse>("/api/tools/validate", {
    method: "POST",
    body: JSON.stringify({ tools }),
  });
}


export async function fetchDatasets(): Promise<DatasetsResponse> {
  return request<DatasetsResponse>("/api/datasets");
}


export async function importDataset(file: File): Promise<{ imported: boolean; dataset: DatasetSummary }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/datasets/import", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Dataset import failed.");
  }

  return response.json() as Promise<{ imported: boolean; dataset: DatasetSummary }>;
}


export async function bootstrapDataset(datasetName: string): Promise<DatasetBootstrapResponse> {
  return request<DatasetBootstrapResponse>("/api/datasets/bootstrap", {
    method: "POST",
    body: JSON.stringify({ dataset_name: datasetName }),
  });
}


export async function createManualDataset(datasetName: string, content: string): Promise<DatasetMutationResponse> {
  return request<DatasetMutationResponse>("/api/datasets/manual", {
    method: "POST",
    body: JSON.stringify({ dataset_name: datasetName, content }),
  });
}


export async function fetchDatasetDetails(datasetName: string, limit = 8): Promise<DatasetDetailResponse> {
  return request<DatasetDetailResponse>(`/api/datasets/${encodeURIComponent(datasetName)}/preview?limit=${limit}`);
}


export async function validateDataset(datasetName: string): Promise<DatasetValidationReport> {
  return request<DatasetValidationReport>(`/api/datasets/${encodeURIComponent(datasetName)}/validate`, {
    method: "POST",
  });
}


export async function appendDatasetRows(datasetName: string, content: string): Promise<DatasetMutationResponse> {
  return request<DatasetMutationResponse>(`/api/datasets/${encodeURIComponent(datasetName)}/append`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}


export async function duplicateDataset(datasetName: string): Promise<DatasetDuplicateResponse> {
  return request<DatasetDuplicateResponse>(`/api/datasets/${encodeURIComponent(datasetName)}/duplicate`, {
    method: "POST",
  });
}


export async function deleteDataset(datasetName: string): Promise<DatasetDeleteResponse> {
  return request<DatasetDeleteResponse>(`/api/datasets/${encodeURIComponent(datasetName)}`, {
    method: "DELETE",
  });
}


export function getDatasetDownloadUrl(datasetName: string): string {
  return `/api/datasets/${encodeURIComponent(datasetName)}/download`;
}


export async function fetchTrainingStatus(): Promise<TrainingStatus> {
  return request<TrainingStatus>("/api/training/status");
}


export async function startTraining(payload: TrainingStartPayload): Promise<TrainingStatus> {
  return request<TrainingStatus>("/api/training/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


export async function runTest(payload: TestRunPayload): Promise<TestResponse> {
  return request<TestResponse>("/api/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


export async function importModelArtifacts(params: {
  checkpointFile: File;
  tokenizerFile: File;
  vocabFile?: File | null;
  outputRootDir: string;
  artifactName: string;
}): Promise<ModelImportResponse> {
  const formData = new FormData();
  formData.append("checkpoint", params.checkpointFile);
  formData.append("tokenizer", params.tokenizerFile);
  if (params.vocabFile) {
    formData.append("vocab", params.vocabFile);
  }
  formData.append("output_root_dir", params.outputRootDir);
  formData.append("artifact_name", params.artifactName);

  const response = await fetch("/api/models/import", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Model import failed.");
  }

  return response.json() as Promise<ModelImportResponse>;
}


export async function fetchLogs(): Promise<LogsResponse> {
  return request<LogsResponse>("/api/logs");
}


export async function exportFailedCases(): Promise<LogsExportResponse> {
  return request<LogsExportResponse>("/api/logs/export-failed-cases", {
    method: "POST",
  });
}
