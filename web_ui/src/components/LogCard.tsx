import { useState } from "react";
import { Badge, Button, Card, Collapse, Group, Stack, Text } from "@mantine/core";
import { IconChevronDown, IconChevronRight, IconCode } from "@tabler/icons-react";

import type { LogRow } from "../api";
import { HighlightedJson } from "./HighlightedJson";


type LogCardProps = {
  row: LogRow;
};


function formatLogTime(value: string | null): string {
  if (!value) {
    return "time unknown";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(timestamp));
}


function resultColor(result: string): string {
  if (result === "tool_call" || result === "success") {
    return "green";
  }
  if (result === "failed" || result === "error") {
    return "red";
  }
  return "gray";
}


export function LogCard({ row }: LogCardProps) {
  const [rawOpen, setRawOpen] = useState(false);
  const hasError = Boolean(row.error && row.error !== "none");
  const showResultBadge = row.result && row.result !== "fallback";

  return (
    <Card>
      <Stack>
        <Group justify="space-between" align="flex-start">
          <div>
            <Text size="xs" tt="uppercase" c="dimmed" fw={700}>{formatLogTime(row.created_at)}</Text>
            <Text fw={700}>{row.user}</Text>
          </div>
          {showResultBadge ? (
            <Badge color={resultColor(row.result)}>{row.result.replace("_", " ")}</Badge>
          ) : null}
        </Group>

        {hasError ? (
          <Card bg="dark.7">
            <Text size="sm" c="dimmed">Error</Text>
            <Text size="sm">{row.error}</Text>
          </Card>
        ) : null}

        {row.raw_output ? (
          <Stack gap={6}>
            <Button
              variant="subtle"
              color="gray"
              justify="flex-start"
              className="raw-output-toggle"
              leftSection={rawOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
              rightSection={<IconCode size={16} />}
              onClick={() => setRawOpen((current) => !current)}
            >
              Raw model output
            </Button>
            <Collapse in={rawOpen}>
              {rawOpen ? <HighlightedJson value={row.raw_output} /> : null}
            </Collapse>
          </Stack>
        ) : null}
      </Stack>
    </Card>
  );
}
