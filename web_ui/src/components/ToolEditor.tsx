import { useMemo, useState } from "react";

import type { ToolDefinition, ToolsSource } from "../api";


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
    JSON.stringify(tool.arguments_schema, null, 2),
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
      const parsed = JSON.parse(nextValue) as Record<string, unknown>;
      reportSchemaError(null);
      onChange({
        ...tool,
        arguments_schema: parsed,
      });
    } catch (error) {
      reportSchemaError(error instanceof Error ? error.message : "Invalid JSON schema.");
    }
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

        <label className="field field--wide">
          <span>Argument schema</span>
          <textarea
            className="code-input"
            value={schemaText}
            onChange={(event) => handleSchemaChange(event.target.value)}
            spellCheck={false}
            rows={14}
          />
          {schemaError ? <small className="field-error">{schemaError}</small> : null}
        </label>
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
