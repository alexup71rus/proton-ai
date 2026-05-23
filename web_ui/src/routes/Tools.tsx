import { useEffect, useState } from "react";

import {
  fetchTools,
  saveTools,
  type ToolDefinition,
  type ToolsSource,
  validateTools,
} from "../api";
import { type EditorFeedback, ToolEditor } from "../components/ToolEditor";
import { ToolList } from "../components/ToolList";


function blankTool(nextIndex: number): ToolDefinition {
  return {
    name: `tool_${nextIndex + 1}`,
    description: "",
    tags: [],
    arguments_schema: {
      type: "object",
      properties: {},
      required: [],
    },
  };
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
  const [actionState, setActionState] = useState<"idle" | "validating" | "saving">("idle");

  async function loadRegistry() {
    setLoadState("loading");
    setLoadError(null);
    try {
      const response = await fetchTools();
      setTools(response.tools);
      setSource(response.source);
      setSelectedIndex(0);
      setDirty(false);
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

  function updateSelectedTool(nextTool: ToolDefinition) {
    setTools((currentTools) =>
      currentTools.map((tool, index) => (index === selectedIndex ? nextTool : tool)),
    );
    setDirty(true);
    setFeedback(null);
  }

  function handleAddTool() {
    const nextIndex = tools.length;
    setTools((currentTools) => [...currentTools, blankTool(currentTools.length)]);
    setSelectedIndex(nextIndex);
    setDirty(true);
    setFeedback({
      tone: "info",
      title: "New tool ready",
      body: "Give it a name, shape the schema, then validate before saving.",
    });
    setSchemaError(null);
  }

  async function handleValidate() {
    setActionState("validating");
    setFeedback(null);
    try {
      const response = await validateTools(tools);
      setFeedback({
        tone: "success",
        title: "Registry looks valid",
        body: `${response.tool_count} tools passed the current service validation rules.`,
      });
    } catch (error) {
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
      const response = await saveTools(tools);
      setTools(response.tools);
      setSource(response.source);
      setDirty(false);
      setFeedback({
        tone: "success",
        title: "Registry saved",
        body: `Source of truth updated in ${response.source.name}.`,
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

  if (loadState === "loading") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <span className="eyebrow">Step 01</span>
            <h1>Tools</h1>
            <p>Load the registry and prepare a clean source of truth for the router.</p>
          </div>
        </header>
        <div className="panel panel--soft empty-state">
          <h2>Loading tools registry</h2>
          <p>Fetching the current file-backed registry from the new UI backend.</p>
        </div>
      </section>
    );
  }

  if (loadState === "error") {
    return (
      <section className="page">
        <header className="page-header">
          <div>
            <span className="eyebrow">Step 01</span>
            <h1>Tools</h1>
            <p>Load the registry and prepare a clean source of truth for the router.</p>
          </div>
        </header>
        <div className="panel empty-state empty-state--error">
          <h2>Could not load the registry</h2>
          <p>{loadError}</p>
          <button className="button button--primary" type="button" onClick={() => void loadRegistry()}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Step 01</span>
          <h1>Tools</h1>
          <p>
            Edit the registry as a real source of truth, validate it in place, and keep the file readable.
          </p>
        </div>
        <div className="page-header__meta">
          <span className="pill">{tools.length} tools</span>
          <span className={`pill${dirty ? " pill--warning" : " pill--soft"}`}>
            {dirty ? "Unsaved changes" : "Registry synced"}
          </span>
        </div>
      </header>

      <div className="tools-layout">
        <ToolList
          tools={tools}
          selectedIndex={selectedIndex}
          dirty={dirty}
          onAdd={handleAddTool}
          onSelect={setSelectedIndex}
        />

        {selectedTool ? (
          <ToolEditor
            key={selectedIndex}
            tool={selectedTool}
            source={source}
            dirty={dirty}
            actionState={actionState}
            feedback={feedback}
            onChange={updateSelectedTool}
            onSchemaValidityChange={setSchemaError}
            onValidate={() => void handleValidate()}
            onSave={() => void handleSave()}
          />
        ) : (
          <section className="panel empty-state">
            <h2>Start the registry</h2>
            <p>Add the first tool to shape the contract the model will learn from.</p>
            <button className="button button--primary" onClick={handleAddTool} type="button">
              Add first tool
            </button>
          </section>
        )}
      </div>

      {schemaError ? (
        <p className="page-note">Fix the schema JSON before validating or saving the registry.</p>
      ) : null}
    </section>
  );
}
