import { useEffect, useState } from "react";
import { Alert, Button, Card, Group, Loader, Modal, Stack, Text, Title } from "@mantine/core";
import { IconAlertCircle, IconRefresh, IconTrash } from "@tabler/icons-react";

import {
  fetchTools,
  saveTools,
  type ToolDefinition,
  type ToolsSource,
  validateTools,
} from "../api";
import { type EditorFeedback, ToolEditor } from "../components/ToolEditor";
import { ToolList } from "../components/ToolList";


type ValidationState = "unknown" | "valid" | "invalid";


function blankTool(): ToolDefinition {
  return {
    name: "",
    description: "",
    tags: [],
    executor_path: "",
    arguments_schema: {
      type: "object",
      properties: {},
      required: [],
    },
  };
}


function compactPath(path: string | undefined): string {
  if (!path) {
    return "data/tools/tools.json";
  }
  const marker = "/proton-x/";
  const markerIndex = path.indexOf(marker);
  if (markerIndex >= 0) {
    return path.slice(markerIndex + marker.length);
  }
  return path;
}


function isValidToolName(name: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(name);
}


function hasBlockingToolIssue(tool: ToolDefinition): boolean {
  const name = tool.name.trim();
  return !name || !isValidToolName(name) || !tool.executor_path.trim();
}


function getDuplicateToolName(tools: ToolDefinition[]): string | null {
  const seen = new Set<string>();
  for (const tool of tools) {
    const name = tool.name.trim();
    if (!name) {
      continue;
    }
    if (seen.has(name)) {
      return name;
    }
    seen.add(name);
  }
  return null;
}


export function ToolsRoute() {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [source, setSource] = useState<ToolsSource | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<EditorFeedback | null>(null);
  const [dirty, setDirty] = useState(false);
  const [validationState, setValidationState] = useState<ValidationState>("valid");
  const [actionState, setActionState] = useState<"idle" | "validating" | "saving">("idle");
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editorVersion, setEditorVersion] = useState(0);

  async function loadRegistry() {
    setLoadState("loading");
    setLoadError(null);
    try {
      const response = await fetchTools();
      setTools(response.tools);
      setSource(response.source);
      setSelectedIndex(0);
      setEditorVersion((version) => version + 1);
      setDirty(false);
      setValidationState("valid");
      setFeedback(null);
      setSchemaError(null);
      setLoadState("ready");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load tools.");
      setLoadState("error");
    }
  }

  useEffect(() => {
    void loadRegistry();
  }, []);

  const selectedTool = tools[selectedIndex] ?? null;
  const registryBlockingMessage = (() => {
    const duplicateName = getDuplicateToolName(tools);
    if (duplicateName) {
      return `Duplicate tool name: ${duplicateName}.`;
    }

    const otherIssueCount = tools.filter((tool, index) => index !== selectedIndex && hasBlockingToolIssue(tool)).length;
    if (otherIssueCount > 0) {
      return otherIssueCount === 1
        ? "Another tool in the list still needs a valid name and executor."
        : `${otherIssueCount} other tools still need a valid name and executor.`;
    }

    return null;
  })();

  function updateSelectedTool(nextTool: ToolDefinition) {
    setTools((currentTools) =>
      currentTools.map((tool, index) => (index === selectedIndex ? nextTool : tool)),
    );
    setDirty(true);
    setValidationState("unknown");
    setFeedback(null);
  }

  function handleAddTool() {
    const nextIndex = tools.length;
    setTools((currentTools) => [...currentTools, blankTool()]);
    setSelectedIndex(nextIndex);
    setEditorVersion((version) => version + 1);
    setDirty(true);
    setValidationState("unknown");
    setFeedback({
      tone: "info",
      title: "Draft tool",
      body: "Fill name, executor, routing tags and attributes, then save.",
    });
    setSchemaError(null);
  }

  async function handleValidate() {
    setActionState("validating");
    setFeedback(null);
    try {
      await validateTools(tools);
      setValidationState("valid");
      setFeedback(null);
    } catch (error) {
      setValidationState("invalid");
      setFeedback({
        tone: "error",
        title: "Validation failed",
        body: error instanceof Error ? error.message : "The service rejected the current registry.",
      });
    } finally {
      setActionState("idle");
    }
  }

  async function handleSave() {
    setActionState("saving");
    setFeedback(null);
    try {
      await validateTools(tools);
      setValidationState("valid");
    } catch (error) {
      setValidationState("invalid");
      setFeedback({
        tone: "error",
        title: "Validation failed",
        body: error instanceof Error ? error.message : "The service rejected the current registry.",
      });
      setActionState("idle");
      return;
    }

    try {
      const response = await saveTools(tools);
      setTools(response.tools);
      setSource(response.source);
      setDirty(false);
      setFeedback({
        tone: "success",
        title: "Registry saved",
        body: `Updated ${response.source.name}.`,
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: "Save failed",
        body: error instanceof Error ? error.message : "Could not persist the registry file.",
      });
    } finally {
      setActionState("idle");
    }
  }

  function handleSelectTool(index: number) {
    setSelectedIndex(index);
    setSchemaError(null);
  }

  function handleDeleteSelectedTool() {
    if (!selectedTool) {
      return;
    }

    const deletedName = selectedTool.name.trim() || "Untitled draft";
    const nextTools = tools.filter((_, index) => index !== selectedIndex);
    const nextIndex = Math.max(0, Math.min(selectedIndex, nextTools.length - 1));

    setTools(nextTools);
    setSelectedIndex(nextIndex);
    setEditorVersion((version) => version + 1);
    setSchemaError(null);
    setValidationState("unknown");
    setDirty(true);
    setDeleteModalOpen(false);
    setFeedback({
      tone: "info",
      title: "Tool removed",
      body: `${deletedName} was removed from the draft registry. Save to persist the change.`,
    });
  }

  if (loadState === "loading") {
    return (
      <Card>
        <Group>
          <Loader size="sm" />
          <Text>Loading tools registry...</Text>
        </Group>
      </Card>
    );
  }

  if (loadState === "error") {
    return (
      <Stack>
        <Alert color="red" title="Could not load registry" icon={<IconAlertCircle size={18} />}>
          {loadError}
        </Alert>
        <Button leftSection={<IconRefresh size={16} />} onClick={() => void loadRegistry()}>
          Retry
        </Button>
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Modal
        opened={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Delete tool?"
        centered
      >
        <Stack>
          <Text size="sm" c="dimmed">
            This removes {selectedTool?.name.trim() || "the draft tool"} from the registry draft. Save the registry afterwards to write it to disk.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteModalOpen(false)}>Cancel</Button>
            <Button color="red" leftSection={<IconTrash size={16} />} onClick={handleDeleteSelectedTool}>
              Delete tool
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Tools registry</Title>
          <Text c="dimmed" size="sm">{compactPath(source?.path)}</Text>
        </div>
      </Group>

      <div className="route-grid route-grid--tools">
        <ToolList
          tools={tools}
          selectedIndex={selectedIndex}
          dirty={dirty}
          onAdd={handleAddTool}
          onSelect={handleSelectTool}
        />

        {selectedTool ? (
          <ToolEditor
            key={`${selectedIndex}-${editorVersion}`}
            tool={selectedTool}
            source={source}
            dirty={dirty}
            actionState={actionState}
            feedback={feedback}
            validationState={validationState}
            registryBlockingMessage={registryBlockingMessage}
            onChange={updateSelectedTool}
            onDelete={() => setDeleteModalOpen(true)}
            onSchemaValidityChange={setSchemaError}
            onValidate={() => void handleValidate()}
            onSave={() => void handleSave()}
          />
        ) : (
          <Card>
            <Stack align="flex-start">
              <Title order={3}>No tools</Title>
              <Text c="dimmed">Start the registry with one tool.</Text>
              <Button onClick={handleAddTool}>Add first tool</Button>
            </Stack>
          </Card>
        )}
      </div>

      {schemaError ? (
        <Alert color="red" icon={<IconAlertCircle size={18} />}>{schemaError}</Alert>
      ) : null}
    </Stack>
  );
}
