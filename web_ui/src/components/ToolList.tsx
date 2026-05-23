import type { ToolDefinition } from "../api";


type ToolListProps = {
  tools: ToolDefinition[];
  selectedIndex: number;
  dirty: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
};


export function ToolList({ tools, selectedIndex, dirty, onSelect, onAdd }: ToolListProps) {
  return (
    <section className="panel tool-list">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Registry</span>
          <h2>Tools</h2>
        </div>
        <div className="tool-list__meta">
          <span className="pill">{tools.length} total</span>
          {dirty ? <span className="pill pill--warning">Unsaved</span> : null}
        </div>
      </div>

      <button className="button button--primary tool-list__add" onClick={onAdd} type="button">
        Add tool
      </button>

      {tools.length === 0 ? (
        <div className="empty-state empty-state--compact">
          <h3>No tools yet</h3>
          <p>Start the registry with one tool and shape the schema from there.</p>
        </div>
      ) : (
        <ul className="tool-list__items">
          {tools.map((tool, index) => (
            <li key={`${tool.name}-${index}`}>
              <button
                className={`tool-list__item${selectedIndex === index ? " tool-list__item--active" : ""}`}
                onClick={() => onSelect(index)}
                type="button"
              >
                <div className="tool-list__item-top">
                  <strong>{tool.name || `tool_${index + 1}`}</strong>
                  <span className="pill pill--soft">{tool.tags.length} tags</span>
                </div>
                <span>{tool.description || "No description yet."}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
