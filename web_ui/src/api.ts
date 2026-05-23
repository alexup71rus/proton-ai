export interface ToolDefinition {
  name: string;
  description: string;
  tags: string[];
  arguments_schema: Record<string, unknown>;
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
}


export interface DatasetsResponse {
  datasets: DatasetSummary[];
}


export interface GenerateDatasetResponse {
  generated: boolean;
  rows_written: number;
  dataset: DatasetSummary;
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
  checkpoint_path: string | null;
  model_path: string | null;
  tokenizer_path: string | null;
}


export interface TrainingStartPayload {
  dataset_name: string;
  epochs: number;
  batch_size: number;
  model_name: string;
  tokenizer_name: string;
}


export interface TestResponse {
  result: {
    status: string;
    tool_name: string | null;
    arguments: Record<string, unknown> | null;
    response: string | null;
  };
  debug: {
    candidate_tools: string[];
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


export async function generateDataset(): Promise<GenerateDatasetResponse> {
  return request<GenerateDatasetResponse>("/api/datasets/generate", {
    method: "POST",
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


export async function runTest(userText: string, answerAllowed = false): Promise<TestResponse> {
  return request<TestResponse>("/api/test", {
    method: "POST",
    body: JSON.stringify({ user_text: userText, answer_allowed: answerAllowed }),
  });
}


export async function fetchLogs(): Promise<LogsResponse> {
  return request<LogsResponse>("/api/logs");
}
