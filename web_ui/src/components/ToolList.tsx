import { useMemo, useState } from "react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconPlus, IconSearch, IconX } from "@tabler/icons-react";

import type { ToolDefinition } from "../api";


type ToolListProps = {
  tools: ToolDefinition[];
  selectedIndex: number;
  dirty: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
};


function collectSchemaText(value: unknown): string[] {
  if (value == null) {
    return [];
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }
  if (Array.isArray(value)) {
    return value.flatMap(collectSchemaText);
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) => [
      key,
      ...collectSchemaText(item),
    ]);
  }
  return [];
}


function matchesTool(tool: ToolDefinition, query: string): boolean {
  const haystack = [
    tool.name,
    tool.description,
    tool.executor_path,
    ...tool.tags,
    ...collectSchemaText(tool.arguments_schema),
  ].join(" ").toLowerCase();

  return haystack.includes(query);
}


function getAttributeCount(tool: ToolDefinition): number {
  const properties = tool.arguments_schema?.properties;
  return properties && typeof properties === "object" ? Object.keys(properties).length : 0;
}


function toolDisplayName(tool: ToolDefinition): string {
  return tool.name.trim() || "Untitled draft";
}


export function ToolList({ tools, selectedIndex, dirty, onSelect, onAdd }: ToolListProps) {
  const [query, setQuery] = useState("");
  const filteredTools = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return tools.map((tool, index) => ({ tool, index }));
    }
    return tools
      .map((tool, index) => ({ tool, index }))
      .filter(({ tool }) => matchesTool(tool, normalized));
  }, [query, tools]);
  const selectedHidden = query.trim() !== "" && !filteredTools.some(({ index }) => index === selectedIndex);
  const selectedTool = tools[selectedIndex];

  return (
    <Card className="sticky-sidebar">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap={8} align="center">
              <Title order={3}>Tools</Title>
              <Badge variant="light">
                {filteredTools.length === tools.length ? tools.length : `${filteredTools.length} / ${tools.length}`}
              </Badge>
            </Group>
            <Group gap={6} mt={6}>
              {dirty ? <Badge color="yellow">unsaved</Badge> : null}
            </Group>
          </div>
          <Button size="xs" leftSection={<IconPlus size={15} />} onClick={onAdd}>
            New tool
          </Button>
        </Group>

        <TextInput
          leftSection={<IconSearch size={16} />}
          rightSection={
            query ? (
              <ActionIcon
                size="sm"
                variant="subtle"
                color="gray"
                aria-label="Clear search"
                onClick={() => setQuery("")}
              >
                <IconX size={14} />
              </ActionIcon>
            ) : null
          }
          rightSectionWidth={query ? 34 : undefined}
          placeholder="Search names, tags, args, enums"
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
        />

        {selectedHidden && selectedTool ? (
          <Alert color="yellow" icon={<IconAlertCircle size={16} />}>
            <Group justify="space-between" gap="xs">
              <Text size="sm">Selected tool is hidden by search: {toolDisplayName(selectedTool)}</Text>
              <Button size="compact-xs" variant="light" onClick={() => setQuery("")}>
                Clear
              </Button>
            </Group>
          </Alert>
        ) : null}

        {filteredTools.length === 0 ? (
          <Text size="sm" c="dimmed">No tools found.</Text>
        ) : (
          <ScrollArea.Autosize mah="calc(100vh - 260px)">
            <Stack gap={6}>
              {filteredTools.map(({ tool, index }) => (
                <Card
                  key={`${tool.name}-${index}`}
                  padding="sm"
                  radius="sm"
                  className="tool-row"
                  data-active={selectedIndex === index}
                  onClick={() => onSelect(index)}
                >
                  <Stack gap={4}>
                    <Group justify="space-between" wrap="nowrap" align="flex-start">
                      <Text fw={650} size="sm" lineClamp={1}>
                        {toolDisplayName(tool)}
                      </Text>
                      {tool.name.trim() ? null : <Badge size="xs" color="yellow">draft</Badge>}
                    </Group>
                    <Text size="xs" c="dimmed" lineClamp={2}>
                      {tool.description || tool.executor_path || "No description yet"}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {tool.tags.length} tags · {getAttributeCount(tool)} attributes
                    </Text>
                  </Stack>
                </Card>
              ))}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Stack>
    </Card>
  );
}
