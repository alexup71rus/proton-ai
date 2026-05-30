import { useMemo, useState } from "react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Collapse,
  Code,
  Divider,
  Group,
  Menu,
  SimpleGrid,
  Stack,
  TagsInput,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconAlertCircle, IconCheck, IconChevronDown, IconChevronRight, IconPlus, IconTrash } from "@tabler/icons-react";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";

import type {
  JsonSchemaStringArgument,
  ToolArgumentsSchema,
  ToolDefinition,
  ToolsSource,
} from "../api";
import { HighlightedJson } from "./HighlightedJson";


type FeedbackTone = "success" | "error" | "info";
type ValidationState = "unknown" | "valid" | "invalid";


export type EditorFeedback = {
  tone: FeedbackTone;
  title: string;
  body?: string;
};


type ToolEditorProps = {
  tool: ToolDefinition;
  source: ToolsSource | null;
  dirty: boolean;
  actionState: "idle" | "validating" | "saving";
  feedback: EditorFeedback | null;
  validationState: ValidationState;
  registryBlockingMessage: string | null;
  onChange: (tool: ToolDefinition) => void;
  onDelete: () => void;
  onSchemaValidityChange: (error: string | null) => void;
  onValidate: () => void;
  onSave: () => void;
};


type AllowedValueRow = {
  value: string;
  description: string;
};


type ArgumentEditorRow = {
  name: string;
  description: string;
  required: boolean;
  enumRows: AllowedValueRow[];
};


type ArgumentTemplate = {
  label: string;
  row: ArgumentEditorRow;
};


const argumentTemplates: ArgumentTemplate[] = [
  {
    label: "directory",
    row: {
      name: "directory",
      description: "Какую разрешённую директорию использовать.",
      required: true,
      enumRows: [
        { value: "downloads", description: "папка загрузок текущего пользователя" },
        { value: "project_root", description: "корень проекта" },
        { value: "data", description: "локальные данные и артефакты" },
      ],
    },
  },
  {
    label: "target",
    row: {
      name: "target",
      description: "Какую цель или подкоманду выбрать.",
      required: true,
      enumRows: [
        { value: "node", description: "версия Node.js через node --version" },
        { value: "npm", description: "версия npm через npm --version" },
      ],
    },
  },
  {
    label: "state",
    row: {
      name: "state",
      description: "Какое состояние применить или показать.",
      required: true,
      enumRows: [
        { value: "on", description: "включить" },
        { value: "off", description: "выключить" },
      ],
    },
  },
  {
    label: "mode",
    row: {
      name: "mode",
      description: "Какой режим выполнения выбрать.",
      required: false,
      enumRows: [
        { value: "short", description: "краткий вывод" },
        { value: "full", description: "подробный вывод" },
      ],
    },
  },
];


function formatSchema(schema: ToolArgumentsSchema): string {
  return JSON.stringify(schema, null, 2);
}


function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}


function asToolArgumentsSchema(value: unknown): ToolArgumentsSchema | null {
  return isRecord(value) ? (value as ToolArgumentsSchema) : null;
}


function getSchemaProperties(schema: ToolArgumentsSchema): Record<string, JsonSchemaStringArgument> {
  const properties = schema.properties as unknown;
  return isRecord(properties) ? (properties as Record<string, JsonSchemaStringArgument>) : {};
}


function getSchemaRequired(schema: ToolArgumentsSchema): string[] {
  const required = schema.required as unknown;
  return Array.isArray(required)
    ? required.filter((value): value is string => typeof value === "string")
    : [];
}


function splitLegacyAllowedValue(value: string): AllowedValueRow {
  const [candidate, ...descriptionParts] = value.split(":");
  if (descriptionParts.length > 0 && candidate.trim()) {
    return {
      value: candidate.trim(),
      description: descriptionParts.join(":").trim(),
    };
  }
  return { value: value.trim(), description: "" };
}


function getAllowedValueRows(value: unknown): AllowedValueRow[] {
  if (isRecord(value)) {
    return Object.entries(value)
      .map(([rawValue, rawDescription]) => ({
        value: rawValue.trim(),
        description: typeof rawDescription === "string" ? rawDescription.trim() : "",
      }))
      .filter((row) => row.value);
  }

  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === "string")
      .map(splitLegacyAllowedValue)
      .filter((row) => row.value);
  }

  return [];
}


function schemaToArgumentRows(schema: ToolArgumentsSchema): ArgumentEditorRow[] {
  const requiredNames = new Set(getSchemaRequired(schema));

  return Object.entries(getSchemaProperties(schema)).map(([name, definition]) => ({
    name,
    description: typeof definition.description === "string" ? definition.description : "",
    required: requiredNames.has(name),
    enumRows: getAllowedValueRows(definition.enum),
  }));
}


function normalizeAllowedValueRows(rows: AllowedValueRow[]): AllowedValueRow[] {
  const seen = new Set<string>();
  const values: AllowedValueRow[] = [];

  for (const row of rows) {
    const value = row.value.trim();
    const description = row.description.trim();
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    values.push({ value, description });
  }

  return values;
}


function buildAllowedValueMap(rows: AllowedValueRow[]): Record<string, string> | null {
  const normalizedRows = normalizeAllowedValueRows(rows);
  if (normalizedRows.length === 0) {
    return null;
  }

  return Object.fromEntries(
    normalizedRows.map((row) => [row.value, row.description]),
  );
}


function allowedOutputValues(rows: AllowedValueRow[]): string[] {
  return normalizeAllowedValueRows(rows).map((row) => row.value);
}


function validateArgumentRows(rows: ArgumentEditorRow[]): string | null {
  const seenNames = new Set<string>();

  for (const row of rows) {
    const name = row.name.trim();
    if (!name) {
      return "Argument name is required.";
    }
    if (seenNames.has(name)) {
      return `Argument "${name}" is duplicated.`;
    }
    seenNames.add(name);

    const seenAllowedValues = new Set<string>();
    for (const enumRow of row.enumRows) {
      const value = enumRow.value.trim();
      const description = enumRow.description.trim();
      if (!value && !description) {
        continue;
      }
      if (!value) {
        return `Allowed value key is required for argument "${name}".`;
      }
      if (seenAllowedValues.has(value)) {
        return `Allowed value "${value}" is duplicated in argument "${name}".`;
      }
      seenAllowedValues.add(value);
    }
  }

  return null;
}


function buildSchemaFromArgumentRows(
  schema: ToolArgumentsSchema,
  rows: ArgumentEditorRow[],
): ToolArgumentsSchema {
  const properties: Record<string, JsonSchemaStringArgument> = {};
  const required: string[] = [];

  for (const row of rows) {
    const name = row.name.trim();
    const description = row.description.trim();
    const enumValues = buildAllowedValueMap(row.enumRows);
    const property: JsonSchemaStringArgument = {
      type: "string",
    };

    if (description) {
      property.description = description;
    }
    if (enumValues) {
      property.enum = enumValues;
    }

    properties[name] = property;
    if (row.required) {
      required.push(name);
    }
  }

  return {
    ...schema,
    type: "object",
    properties,
    required,
  };
}


function getNextArgumentName(rows: ArgumentEditorRow[]): string {
  const existingNames = new Set(rows.map((row) => row.name.trim()).filter(Boolean));
  const commonNames = ["target", "state", "directory", "mode", "query", "path"];
  const availableCommonName = commonNames.find((name) => !existingNames.has(name));

  if (availableCommonName) {
    return availableCommonName;
  }

  if (!existingNames.has("custom_arg")) {
    return "custom_arg";
  }

  let index = 2;
  let candidate = `custom_arg_${index}`;

  while (existingNames.has(candidate)) {
    index += 1;
    candidate = `custom_arg_${index}`;
  }

  return candidate;
}


function makeUniqueArgumentName(name: string, rows: ArgumentEditorRow[]): string {
  const existingNames = new Set(rows.map((row) => row.name.trim()).filter(Boolean));
  if (!existingNames.has(name)) {
    return name;
  }

  let index = 2;
  let candidate = `${name}_${index}`;
  while (existingNames.has(candidate)) {
    index += 1;
    candidate = `${name}_${index}`;
  }
  return candidate;
}


function compactPath(path: string | undefined): string {
  if (!path) {
    return "";
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


function getEditorIssues(tool: ToolDefinition, rows: ArgumentEditorRow[]): string[] {
  const issues: string[] = [];
  const name = tool.name.trim();
  const executorPath = tool.executor_path.trim();

  if (!name) {
    issues.push("Set a tool name before validating or saving.");
  } else if (!isValidToolName(name)) {
    issues.push("Tool name should use letters, numbers and underscores, and cannot start with a number.");
  }
  if (!executorPath) {
    issues.push("Set an executor path before validating or saving.");
  }

  const rowValidationError = validateArgumentRows(rows);
  if (rowValidationError) {
    issues.push(rowValidationError);
  }

  return issues;
}


function buildToolCallPreview(tool: ToolDefinition, rows: ArgumentEditorRow[]): string {
  const argumentsPreview: Record<string, string> = {};

  for (const row of rows) {
    if (!row.required) {
      continue;
    }

    const attributeName = row.name.trim();
    if (!attributeName) {
      continue;
    }

    const enumValues = allowedOutputValues(row.enumRows);
    argumentsPreview[attributeName] = enumValues[0] || `<${attributeName}>`;
  }

  return JSON.stringify(
    {
      tool_calls: [
        {
          name: tool.name.trim() || "<tool_name>",
          arguments: argumentsPreview,
        },
      ],
    },
    null,
    2,
  );
}


function feedbackColor(tone: FeedbackTone): string {
  if (tone === "success") {
    return "green";
  }
  if (tone === "error") {
    return "red";
  }
  return "blue";
}


function readStoredBoolean(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") {
    return fallback;
  }
  const stored = window.localStorage.getItem(key);
  if (stored == null) {
    return fallback;
  }
  return stored === "true";
}


function storeBoolean(key: string, value: boolean) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(key, String(value));
}


function validationBadgeColor(state: ValidationState): string {
  if (state === "valid") {
    return "green";
  }
  if (state === "invalid") {
    return "red";
  }
  return "yellow";
}


function validationBadgeLabel(state: ValidationState): string {
  if (state === "valid") {
    return "validated";
  }
  if (state === "invalid") {
    return "validation failed";
  }
  return "needs validation";
}


export function ToolEditor({
  tool,
  source,
  dirty,
  actionState,
  feedback,
  validationState,
  registryBlockingMessage,
  onChange,
  onDelete,
  onSchemaValidityChange,
  onValidate,
  onSave,
}: ToolEditorProps) {
  const [schemaText, setSchemaText] = useState(formatSchema(tool.arguments_schema));
  const [argumentRows, setArgumentRows] = useState<ArgumentEditorRow[]>(
    schemaToArgumentRows(tool.arguments_schema),
  );
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [rawSchemaOpen, setRawSchemaOpen] = useState(() => readStoredBoolean("protonx.toolEditor.rawSchemaOpen", false));

  const sourceLabel = useMemo(() => source?.name ?? "tools.json", [source]);
  const sourcePathLabel = useMemo(() => compactPath(source?.path), [source]);
  const editorIssues = useMemo(() => getEditorIssues(tool, argumentRows), [argumentRows, tool]);
  const blockingIssues = registryBlockingMessage ? [...editorIssues, registryBlockingMessage] : editorIssues;
  const canRunRegistryAction = actionState === "idle" && !schemaError && blockingIssues.length === 0;
  const canSave = canRunRegistryAction && validationState === "valid" && dirty;
  const toolCallPreview = useMemo(() => buildToolCallPreview(tool, argumentRows), [argumentRows, tool]);

  function reportSchemaError(message: string | null) {
    setSchemaError(message);
    onSchemaValidityChange(message);
  }

  function handleSchemaChange(nextValue: string) {
    setSchemaText(nextValue);
    try {
      const parsed = asToolArgumentsSchema(JSON.parse(nextValue));
      if (!parsed) {
        reportSchemaError("Argument schema must be a JSON object.");
        return;
      }
      reportSchemaError(null);
      setArgumentRows(schemaToArgumentRows(parsed));
      onChange({
        ...tool,
        arguments_schema: parsed,
      });
    } catch (error) {
      reportSchemaError(error instanceof Error ? error.message : "Invalid JSON schema.");
    }
  }

  function commitArgumentRows(nextRows: ArgumentEditorRow[]) {
    const validationError = validateArgumentRows(nextRows);
    if (validationError) {
      setArgumentRows(nextRows);
      reportSchemaError(validationError);
      return;
    }

    const normalizedRows = nextRows.map((row) => ({
      ...row,
      name: row.name.trim(),
      enumRows: row.enumRows.map((enumRow) => ({
        value: enumRow.value.trim(),
        description: enumRow.description.trim(),
      })),
    }));
    const nextSchema = buildSchemaFromArgumentRows(tool.arguments_schema, normalizedRows);

    setArgumentRows(normalizedRows);
    setSchemaText(formatSchema(nextSchema));
    reportSchemaError(null);
    onChange({
      ...tool,
      arguments_schema: nextSchema,
    });
  }

  function updateArgumentRow(index: number, patch: Partial<ArgumentEditorRow>) {
    commitArgumentRows(
      argumentRows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );
  }

  function addArgument(template?: ArgumentEditorRow) {
    const nextRow = template
      ? {
          ...template,
          name: makeUniqueArgumentName(template.name, argumentRows),
        }
      : {
          name: getNextArgumentName(argumentRows),
          description: "",
          required: false,
          enumRows: [],
        };

    commitArgumentRows([
      ...argumentRows,
      nextRow,
    ]);
  }

  function removeArgument(index: number) {
    commitArgumentRows(argumentRows.filter((_, rowIndex) => rowIndex !== index));
  }

  function updateAllowedValueRow(argumentIndex: number, enumIndex: number, patch: Partial<AllowedValueRow>) {
    const argument = argumentRows[argumentIndex];
    if (!argument) {
      return;
    }
    updateArgumentRow(argumentIndex, {
      enumRows: argument.enumRows.map((row, rowIndex) => (rowIndex === enumIndex ? { ...row, ...patch } : row)),
    });
  }

  function addAllowedValueRow(argumentIndex: number) {
    const argument = argumentRows[argumentIndex];
    if (!argument) {
      return;
    }
    updateArgumentRow(argumentIndex, {
      enumRows: [...argument.enumRows, { value: "", description: "" }],
    });
  }

  function removeAllowedValueRow(argumentIndex: number, enumIndex: number) {
    const argument = argumentRows[argumentIndex];
    if (!argument) {
      return;
    }
    updateArgumentRow(argumentIndex, {
      enumRows: argument.enumRows.filter((_, rowIndex) => rowIndex !== enumIndex),
    });
  }

  function insertAllowedValueExample(argumentIndex: number) {
    updateArgumentRow(argumentIndex, {
      enumRows: [
        { value: "on", description: "Включить свет" },
        { value: "off", description: "Выключить свет" },
      ],
    });
  }

  function toggleRawSchema() {
    setRawSchemaOpen((current) => {
      const next = !current;
      storeBoolean("protonx.toolEditor.rawSchemaOpen", next);
      return next;
    });
  }

  return (
    <Card>
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap="xs">
              <Title order={3}>{tool.name.trim() || "Untitled draft"}</Title>
              {dirty ? <Badge color="yellow">unsaved</Badge> : <Badge variant="light">saved</Badge>}
              <Badge color={validationBadgeColor(validationState)} variant="light">
                {validationBadgeLabel(validationState)}
              </Badge>
            </Group>
            <Text size="sm" c="dimmed">
              {sourceLabel}{sourcePathLabel ? ` · ${sourcePathLabel}` : ""}
            </Text>
          </div>

          <Group gap="xs">
            <Button
              variant="light"
              color="red"
              leftSection={<IconTrash size={16} />}
              disabled={actionState !== "idle"}
              onClick={onDelete}
            >
              Delete
            </Button>
            <Button
              disabled={!canSave}
              loading={actionState === "saving"}
              onClick={onSave}
            >
              Save
            </Button>
          </Group>
        </Group>

        {feedback ? (
          <Alert
            color={feedbackColor(feedback.tone)}
            title={feedback.title}
            icon={feedback.tone === "error" ? <IconAlertCircle size={18} /> : <IconCheck size={18} />}
          >
            {feedback.body}
          </Alert>
        ) : null}

        {blockingIssues.length > 0 ? (
          <Alert color="yellow" title="Draft is not ready" icon={<IconAlertCircle size={18} />}>
            {blockingIssues.join(" ")}
          </Alert>
        ) : null}

        {dirty && validationState !== "valid" && blockingIssues.length === 0 && !schemaError ? (
          <Alert color="yellow" title="Validation required" icon={<IconAlertCircle size={18} />}>
            Run Validate in Advanced before saving the registry.
          </Alert>
        ) : null}

        <Stack gap="xs">
          <Title order={4}>Identity</Title>
          <Text size="sm" c="dimmed">Stable name, human description and executor script.</Text>
        </Stack>

        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <TextInput
            label="Name"
            description="Stable id used in model output."
            placeholder="get_node_version"
            error={!tool.name.trim() ? "Required" : !isValidToolName(tool.name.trim()) ? "Use snake_case-style id" : undefined}
            value={tool.name}
            onChange={(event) => onChange({ ...tool, name: event.currentTarget.value })}
          />
          <TextInput
            label="Executor"
            description="Trusted local script called after validation."
            placeholder="web_backend/executors/my_tool.py"
            error={!tool.executor_path.trim() ? "Required" : undefined}
            value={tool.executor_path}
            onChange={(event) => onChange({ ...tool, executor_path: event.currentTarget.value })}
          />
        </SimpleGrid>

        <Textarea
          label="Description"
          description="Human-readable purpose. Keep it short; routing mainly depends on name, tags and attributes."
          autosize
          minRows={2}
          value={tool.description}
          onChange={(event) => onChange({ ...tool, description: event.currentTarget.value })}
        />

        <Divider />

        <Stack gap="xs">
          <Title order={4}>Routing language</Title>
          <Text size="sm" c="dimmed">Add real words users will type: aliases, transliteration, abbreviations and command forms.</Text>
        </Stack>

        <TagsInput
          label="Tags"
          description="Press Enter or comma to add. These are the main lexical hints for the tiny model."
          value={tool.tags}
          onChange={(tags) => onChange({ ...tool, tags })}
          splitChars={[","]}
          clearable
        />

        <Divider />

        <Group justify="space-between">
          <div>
            <Title order={4}>Tool-call attributes</Title>
            <Text size="sm" c="dimmed">
              These become keys inside <Code>tool_calls[0].arguments</Code>. Use enum descriptions to teach the model when to choose each value.
            </Text>
          </div>
          <Menu shadow="md" width={240}>
            <Menu.Target>
              <Button variant="light" leftSection={<IconPlus size={16} />} rightSection={<IconChevronDown size={14} />}>
                Add attribute
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={() => addArgument()}>
                Empty attribute
              </Menu.Item>
              {argumentTemplates.map((template) => (
                <Menu.Item key={template.label} onClick={() => addArgument(template.row)}>
                  {template.label}
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
        </Group>

        {argumentRows.length === 0 ? (
          <Card bg="dark.7" withBorder>
            <Stack align="flex-start" gap="xs">
              <Text size="sm" c="dimmed">
                No attributes. Keep it empty for commands like current time; add attributes for directory, target, mode, state or other choices.
              </Text>
              <Group gap="xs">
                {argumentTemplates.slice(0, 3).map((template) => (
                  <Button
                    key={template.label}
                    size="compact-sm"
                    variant="light"
                    onClick={() => addArgument(template.row)}
                  >
                    {template.label}
                  </Button>
                ))}
                <Button size="compact-sm" variant="default" leftSection={<IconPlus size={15} />} onClick={() => addArgument()}>
                  Empty
                </Button>
              </Group>
            </Stack>
          </Card>
        ) : (
          <Stack>
            {argumentRows.map((argument, index) => {
              const outputValues = allowedOutputValues(argument.enumRows);

              return (
                <Card key={index} bg="dark.7" withBorder>
                  <Stack>
                    <Group justify="space-between" align="flex-start">
                      <SimpleGrid cols={{ base: 1, md: 2 }} style={{ flex: 1 }}>
                        <TextInput
                          label="Attribute key"
                          description="JSON key returned inside tool_calls[0].arguments."
                          value={argument.name}
                          onChange={(event) => updateArgumentRow(index, { name: event.currentTarget.value })}
                        />
                        <Textarea
                          label="Description"
                          description="Short hint for humans and for the routing prompt."
                          autosize
                          minRows={1}
                          value={argument.description}
                          onChange={(event) => updateArgumentRow(index, { description: event.currentTarget.value })}
                        />
                      </SimpleGrid>
                      <Tooltip label="Remove attribute">
                        <ActionIcon color="red" variant="subtle" onClick={() => removeArgument(index)}>
                          <IconTrash size={18} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                    <Group gap="md">
                      <Checkbox
                        checked={argument.required}
                        label="Required attribute"
                        onChange={(event) => updateArgumentRow(index, { required: event.currentTarget.checked })}
                      />
                      <Badge variant="default">string</Badge>
                    </Group>

                    <Group justify="space-between" align="flex-end">
                      <div>
                        <Text size="sm" fw={500}>Allowed values</Text>
                        <Text size="xs" c="dimmed">
                          Optional fixed choices. The model returns the value; the meaning teaches when to use it.
                        </Text>
                      </div>
                      <Badge variant="light">{outputValues.length} values</Badge>
                    </Group>

                    {argument.enumRows.length > 0 ? (
                      <Stack gap="xs">
                        {argument.enumRows.map((enumRow, enumIndex) => (
                          <div className="enum-value-row" key={enumIndex}>
                            <TextInput
                              label={enumIndex === 0 ? "Value" : undefined}
                              placeholder="downloads"
                              value={enumRow.value}
                              onChange={(event) => updateAllowedValueRow(index, enumIndex, { value: event.currentTarget.value })}
                            />
                            <TextInput
                              label={enumIndex === 0 ? "Meaning" : undefined}
                              placeholder="папка загрузок текущего пользователя"
                              value={enumRow.description}
                              onChange={(event) => updateAllowedValueRow(index, enumIndex, { description: event.currentTarget.value })}
                            />
                            <Tooltip label="Remove value">
                              <ActionIcon
                                color="red"
                                variant="subtle"
                                mt={enumIndex === 0 ? 25 : 0}
                                onClick={() => removeAllowedValueRow(index, enumIndex)}
                              >
                                <IconTrash size={17} />
                              </ActionIcon>
                            </Tooltip>
                          </div>
                        ))}
                      </Stack>
                    ) : (
                      <Card bg="dark.6" withBorder>
                        <Group justify="space-between" align="center">
                          <Text size="sm" c="dimmed">No fixed values; any string is accepted for this attribute.</Text>
                          <Button size="compact-sm" variant="light" onClick={() => insertAllowedValueExample(index)}>
                            Insert example
                          </Button>
                        </Group>
                      </Card>
                    )}

                    <Group justify="space-between" align="center">
                      <Button
                        size="compact-sm"
                        variant="default"
                        leftSection={<IconPlus size={15} />}
                        onClick={() => addAllowedValueRow(index)}
                      >
                        Add value
                      </Button>
                      {outputValues.length > 0 ? (
                        <Text size="xs" c="dimmed">
                          Model output: {outputValues.join(", ")}
                        </Text>
                      ) : null}
                    </Group>
                  </Stack>
                </Card>
              );
            })}
          </Stack>
        )}

        <Stack gap="xs">
          <Group justify="space-between" align="center">
            <Title order={4}>Tool-call preview</Title>
            <Badge variant="light">{argumentRows.filter((row) => row.required).length} required</Badge>
          </Group>
          <Text size="sm" c="dimmed">
            This is the JSON shape the tiny router should produce for this tool.
          </Text>
          <HighlightedJson value={toolCallPreview} compact />
        </Stack>

        <Divider />

        <Group justify="space-between">
          <div>
            <Title order={4}>Advanced</Title>
            <Text size="sm" c="dimmed">Raw JSON schema, validation and low-level registry checks.</Text>
          </div>
          <Group gap="xs">
            <Button
              variant="light"
              leftSection={<IconCheck size={16} />}
              disabled={!canRunRegistryAction}
              loading={actionState === "validating"}
              onClick={onValidate}
            >
              Validate
            </Button>
            <Button
              variant="subtle"
              leftSection={rawSchemaOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
              onClick={toggleRawSchema}
            >
              {rawSchemaOpen ? "Hide raw schema" : "Show raw schema"}
            </Button>
          </Group>
        </Group>

        <Collapse in={rawSchemaOpen}>
          <Stack>
            <Stack gap={6}>
              <Text size="sm" fw={500}>Raw schema</Text>
              <CodeMirror
                className="json-code-editor"
                value={schemaText}
                minHeight="260px"
                maxHeight="520px"
                basicSetup={{
                  foldGutter: true,
                  highlightActiveLine: true,
                  lineNumbers: true,
                }}
                extensions={[json()]}
                theme={oneDark}
                onChange={handleSchemaChange}
              />
            </Stack>
          </Stack>
        </Collapse>

        {schemaError ? (
          <Alert color="red" icon={<IconAlertCircle size={18} />}>{schemaError}</Alert>
        ) : null}
      </Stack>
    </Card>
  );
}
