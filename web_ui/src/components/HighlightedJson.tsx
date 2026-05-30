import type { ReactNode } from "react";


type HighlightedJsonProps = {
  value: string;
  compact?: boolean;
};


function highlightJson(text: string): ReactNode[] {
  const matcher = /("(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g;
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let tokenIndex = 0;

  for (const match of text.matchAll(matcher)) {
    const token = match[0];
    const index = match.index ?? 0;
    if (index > cursor) {
      nodes.push(text.slice(cursor, index));
    }

    const nextNonSpace = text.slice(index + token.length).match(/^\s*:/);
    let className = "json-token";
    if (token.startsWith("\"") && nextNonSpace) {
      className += " json-token--key";
    } else if (token.startsWith("\"")) {
      className += " json-token--string";
    } else if (token === "true" || token === "false") {
      className += " json-token--boolean";
    } else if (token === "null") {
      className += " json-token--null";
    } else {
      className += " json-token--number";
    }

    nodes.push(
      <span className={className} key={`${index}-${tokenIndex}`}>
        {token}
      </span>,
    );
    tokenIndex += 1;
    cursor = index + token.length;
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return nodes;
}


export function HighlightedJson({ value, compact = false }: HighlightedJsonProps) {
  return (
    <pre className={`json-block json-highlight${compact ? " json-block--compact" : ""}`}>
      {highlightJson(value)}
    </pre>
  );
}
