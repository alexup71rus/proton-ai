import { useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Stack,
  Switch,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconPlayerPlay, IconX } from "@tabler/icons-react";

import { runTest, type TestResponse, type WorkspaceModel, type WorkspaceTestSettings } from "../api";
import { DebugPanel } from "../components/DebugPanel";
import { usePersistedTestDraft } from "../usePersistedTestDraft";


type TestRouteProps = {
  selectedModel: WorkspaceModel;
  testSettings: WorkspaceTestSettings;
  onTestSettingsChange: (next: WorkspaceTestSettings) => Promise<void>;
};


function formatResultStatus(status: string): string {
  switch (status) {
    case "tool_call":
      return "tool";
    case "fallback":
      return "fallback";
    case "success":
      return "complete";
    case "failed":
      return "failed";
    default:
      return status.split("_").join(" ");
  }
}


const testExamples = [
  "папка загрузок",
  "покажи npm -v",
  "docker ps",
  "как дела",
];


function hasArguments(argumentsPayload: TestResponse["result"]["arguments"]): boolean {
  return Boolean(argumentsPayload && Object.keys(argumentsPayload).length > 0);
}


function executionResponse(result: TestResponse): string | null {
  if (result.result.response) {
    return result.result.response;
  }
  const output = result.result.execution?.output;
  if (!output || typeof output !== "object" || Array.isArray(output)) {
    return null;
  }
  const response = (output as Record<string, unknown>).response;
  return typeof response === "string" && response.trim() ? response.trim() : null;
}


export function TestRoute({ selectedModel, testSettings, onTestSettingsChange }: TestRouteProps) {
  const [result, setResult] = useState<TestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const {
    userText,
    setUserText,
    showDebug,
    setShowDebug,
    settingsError,
  } = usePersistedTestDraft({
    testSettings,
    onTestSettingsChange,
  });
  const modelReady = Boolean(selectedModel.model_path && selectedModel.tokenizer_path);

  async function handleRun() {
    if (!userText.trim()) {
      return;
    }
    setIsRunning(true);
    setError(null);
    try {
      const payload = await runTest({
        user_text: userText,
        model_path: selectedModel.model_path,
        tokenizer_path: selectedModel.tokenizer_path,
      });
      setResult(payload);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error.");
    } finally {
      setIsRunning(false);
    }
  }

  const isFallback = result?.result.status === "fallback";
  const execution = result?.result.execution;
  const resultResponse = result ? executionResponse(result) : null;
  const resultHasArguments = result ? hasArguments(result.result.arguments) : false;

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Test router</Title>
          <Text c="dimmed" size="sm">{selectedModel.label}</Text>
        </div>
        <Badge color={modelReady ? "green" : "yellow"}>
          {modelReady ? "model ready" : "model missing"}
        </Badge>
      </Group>

      {!modelReady ? (
        <Alert color="yellow" title="Load a model first" icon={<IconAlertCircle size={18} />}>
          The selected workspace model needs checkpoint and tokenizer paths.
        </Alert>
      ) : (
        <>
          <Card>
            <Stack>
              <Group justify="space-between">
                <Title order={3}>Request</Title>
                <Switch checked={showDebug} onChange={(event) => setShowDebug(event.currentTarget.checked)} label="Debug details" />
              </Group>

              <Group gap="xs">
                {testExamples.map((example) => (
                  <Button
                    key={example}
                    size="compact-sm"
                    variant="light"
                    onClick={() => {
                      setUserText(example);
                      setResult(null);
                      setError(null);
                    }}
                  >
                    {example}
                  </Button>
                ))}
              </Group>

              <Textarea
                value={userText}
                onChange={(event) => {
                  setUserText(event.currentTarget.value);
                  setResult(null);
                  setError(null);
                }}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    void handleRun();
                  }
                }}
                minRows={3}
                autosize
                placeholder="покажи npm -v"
              />

              <Group justify="space-between">
                <Group gap="xs">
                  <Badge variant="light">Using {selectedModel.label}</Badge>
                  <Text size="xs" c="dimmed">Cmd/Ctrl+Enter runs the request.</Text>
                </Group>
                <Group gap="xs">
                  {userText ? (
                    <Button variant="default" leftSection={<IconX size={15} />} onClick={() => setUserText("")}>
                      Clear
                    </Button>
                  ) : null}
                  <Button
                    leftSection={<IconPlayerPlay size={16} />}
                    disabled={isRunning || !userText.trim()}
                    loading={isRunning}
                    onClick={() => void handleRun()}
                  >
                    Run
                  </Button>
                </Group>
              </Group>
            </Stack>
          </Card>

          {error ? (
            <Alert color="red" title="Request failed" icon={<IconAlertCircle size={18} />}>{error}</Alert>
          ) : null}

          {settingsError ? (
            <Alert color="red" title="Could not save test settings" icon={<IconAlertCircle size={18} />}>{settingsError}</Alert>
          ) : null}

          {showDebug && result ? <DebugPanel debug={result.debug} /> : null}

          {result ? (
            <Card>
              <Stack>
                <Group justify="space-between">
                  <Title order={3}>{isFallback ? "Fallback" : "Tool call"}</Title>
                  <Badge color={isFallback ? "yellow" : "green"}>
                    {formatResultStatus(result.result.status)}
                  </Badge>
                </Group>

                {result.result.validation_error ? (
                  <Alert color="red" title="Model output rejected" icon={<IconAlertCircle size={18} />}>
                    {result.result.validation_error}
                  </Alert>
                ) : null}

                {result.result.tool_name ? (
                  <>
                    <Card bg="dark.7">
                      <Stack gap="sm">
                        <Text size="sm" c="dimmed">Tool</Text>
                        <Text fw={700}>{result.result.tool_name}</Text>
                        {resultHasArguments ? (
                          <>
                            <Text size="sm" c="dimmed">Arguments</Text>
                            <pre className="json-block json-block--compact">{JSON.stringify(result.result.arguments, null, 2)}</pre>
                          </>
                        ) : null}
                      </Stack>
                    </Card>

                    {execution?.error ? (
                      <Alert color="red" title="Execution failed">
                        <Text>{execution.error}</Text>
                      </Alert>
                    ) : null}

                    {resultResponse ? (
                      <Card bg="dark.7">
                        <Text size="sm" c="dimmed">Response</Text>
                        <Text>{resultResponse}</Text>
                      </Card>
                    ) : null}
                  </>
                ) : (
                  <Card bg="dark.7">
                    <Text>{result.result.response || "The router returned fallback."}</Text>
                  </Card>
                )}
              </Stack>
            </Card>
          ) : null}

        </>
      )}
    </Stack>
  );
}
