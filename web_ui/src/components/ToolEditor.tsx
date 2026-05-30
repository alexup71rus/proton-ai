import { useMemo, useState } from "react";

import type {
  JsonSchemaStringArgument,
  ToolArgumentsSchema,
  ToolDefinition,
  ToolsSource,
} from "../api";


type FeedbackTone = "success" | "error" | "info";


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
  onChange: (tool: ToolDefinition) => void;
  onSchemaValidityChange: (error: string | null) => void;
  onValidate: () => void;
  onSave: () => void;
};


type ArgumentEditorRow = {
  name: string;
  description: string;
  required: boolean;
  enumText: string;
};


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


function getStringEnumValues(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}


function schemaToArgumentRows(schema: ToolArgumentsSchema): ArgumentEditorRow[] {
  const requiredNames = new Set(getSchemaRequired(schema));

  return Object.entries(getSchemaProperties(schema)).map(([name, definition]) => ({
    name,
    description: typeof definition.description === "string" ? definition.description : "",
    required: requiredNames.has(name),
    enumText: getStringEnumValues(definition.enum).join("\n"),
  }));
}


function parseEnumValues(value: string): string[] {
  const seen = new Set<string>();
  const values: string[] = [];

  for (const item of value.split(/\r?\n/)) {
    const trimmed = item.trim();
    if (trimmed && !seen.has(trimmed)) {
      seen.add(trimmed);
      values.push(trimmed);
    }
  }

  return values;
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
    const enumValues = parseEnumValues(row.enumText);
    const property: JsonSchemaStringArgument = {
      type: "string",
    };

    if (description) {
      property.description = description;
    }
    if (enumValues.length > 0) {
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
  let index = 1;
  let candidate = `argument_${index}`;

  while (existingNames.has(candidate)) {
    index += 1;
    candidate = `argument_${index}`;
  }

  return candidate;
}


export function ToolEditor({
  tool,
  source,
  dirty,
  actionState,
  feedback,
  onChange,
  onSchemaValidityChange,
  onValidate,
  onSave,
}: ToolEditorProps) {
  const [tagInput, setTagInput] = useState("");
  const [schemaText, setSchemaText] = useState(
    formatSchema(tool.arguments_schema),
  );
  const [argumentRows, setArgumentRows] = useState<ArgumentEditorRow[]>(
    schemaToArgumentRows(tool.arguments_schema),
  );
  const [schemaError, setSchemaError] = useState<string | null>(null);

  const sourceLabel = useMemo(() => source?.name ?? "tools.json", [source]);

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

  function addArgument() {
    commitArgumentRows([
      ...argumentRows,
      {
        name: getNextArgumentName(argumentRows),
        description: "",
        required: false,
        enumText: "",
      },
    ]);
  }

  function removeArgument(index: number) {
    commitArgumentRows(argumentRows.filter((_, rowIndex) => rowIndex !== index));
  }

  function addTag(rawTag: string) {
    const nextTag = rawTag.trim();
    if (!nextTag || tool.tags.includes(nextTag)) {
      return;
    }
    onChange({
      ...tool,
      tags: [...tool.tags, nextTag],
    });
    setTagInput("");
  }

  function removeTag(tag: string) {
    onChange({
      ...tool,
      tags: tool.tags.filter((value) => value !== tag),
    });
  }

  return (
    <section className="panel tool-editor">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Selected tool</span>
          <h2>{tool.name || "Untitled tool"}</h2>
        </div>
        <div className="tool-editor__source">
          <span className="pill pill--soft">Source</span>
          <strong>{sourceLabel}</strong>
          {source ? <span title={source.path}>{source.path}</span> : null}
        </div>
      </div>

      {feedback ? (
        <div className={`feedback feedback--${feedback.tone}`} role="status">
          <strong>{feedback.title}</strong>
          {feedback.body ? <p>{feedback.body}</p> : null}
        </div>
      ) : null}

      <div className="tool-editor__grid">
        <label className="field">
          <span>Name</span>
          <input
            className="input"
            type="text"
            value={tool.name}
            onChange={(event) => onChange({ ...tool, name: event.target.value })}
            placeholder="light"
          />
        </label>

        <label className="field field--wide">
          <span>Description</span>
          <input
            className="input"
            type="text"
            value={tool.description}
            onChange={(event) => onChange({ ...tool, description: event.target.value })}
            placeholder="Light control for on/off commands"
          />
        </label>

        <label className="field field--wide">
          <span>Executor script</span>
          <input
            className="input"
            type="text"
            value={tool.executor_path}
            onChange={(event) => onChange({ ...tool, executor_path: event.target.value })}
            placeholder="web_backend/executors/get_current_time.py"
          />
        </label>

        <div className="field field--wide">
          <span>Tags</span>
          <div className="chips-wrap">
            {tool.tags.map((tag) => (
              <button
                key={tag}
                className="chip"
                type="button"
                onClick={() => removeTag(tag)}
                title="Remove tag"
              >
                {tag}
                <span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
          <div className="tag-input-row">
            <input
              className="input"
              type="text"
              value={tagInput}
              onChange={(event) => setTagInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === ",") {
                  event.preventDefault();
                  addTag(tagInput);
                }
              }}
              placeholder="Type a tag and press Enter"
            />
            <button className="button button--secondary" type="button" onClick={() => addTag(tagInput)}>
              Add tag
            </button>
          </div>
        </div>

        <div className="field field--wide argument-editor">
          <div className="argument-editor__header">
            <span>Arguments</span>
            <button className="button button--secondary" type="button" onClick={addArgument}>
              Add arg
            </button>
          </div>

          {argumentRows.length > 0 ? (
            <div className="argument-list">
              {argumentRows.map((argument, index) => (
                <div className="argument-row" key={`${argument.name}-${index}`}>
                  <div className="argument-row__top">
                    <label className="field">
                      <span>Name</span>
                      <input
                        className="input"
                        type="text"
                        value={argument.name}
                        onChange={(event) => updateArgumentRow(index, { name: event.target.value })}
                        placeholder="state"
                      />
                    </label>

                    <label className="argument-row__required">
                      <input
                        checked={argument.required}
                        onChange={(event) => updateArgumentRow(index, { required: event.target.checked })}
                        type="checkbox"
                      />
                      <span>Required</span>
                    </label>

                    <button
                      className="button button--secondary argument-row__remove"
                      type="button"
                      onClick={() => removeArgument(index)}
                    >
                      Remove
                    </button>
                  </div>

                  <div className="argument-row__grid">
                    <label className="field">
                      <span>Description</span>
                      <input
                        className="input"
                        type="text"
                        value={argument.description}
                        onChange={(event) => updateArgumentRow(index, { description: event.target.value })}
                        placeholder="Target state"
                      />
                    </label>

                    <label className="field">
                      <span>Enum values</span>
                      <textarea
                        className="input enum-input"
                        value={argument.enumText}
                        onChange={(event) => updateArgumentRow(index, { enumText: event.target.value })}
                        placeholder={"on: Включить свет\noff: Выключить свет"}
                        rows={4}
                        spellCheck={false}
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="argument-empty">No arguments defined.</div>
          )}
        </div>

        <details className="field field--wide advanced-schema">
          <summary>Advanced / raw JSON</summary>
          <textarea
            className="code-input"
            value={schemaText}
            onChange={(event) => handleSchemaChange(event.target.value)}
            spellCheck={false}
            rows={14}
          />
        </details>
        {schemaError ? <small className="field-error schema-error">{schemaError}</small> : null}
      </div>

      <div className="action-bar">
        <div className="action-bar__status">
          {dirty ? <span className="pill pill--warning">Changes not saved</span> : <span className="pill pill--soft">In sync</span>}
          {schemaError ? <span className="pill pill--danger">Schema needs fixing</span> : null}
        </div>

        <div className="action-bar__actions">
          <button
            className="button button--secondary"
            disabled={actionState !== "idle" || Boolean(schemaError)}
            onClick={onValidate}
            type="button"
          >
            {actionState === "validating" ? "Validating..." : "Validate"}
          </button>
          <button
            className="button button--primary"
            disabled={actionState !== "idle" || Boolean(schemaError) || !dirty}
            onClick={onSave}
            type="button"
          >
            {actionState === "saving" ? "Saving..." : "Save registry"}
          </button>
        </div>
      </div>
    </section>
  );
}
