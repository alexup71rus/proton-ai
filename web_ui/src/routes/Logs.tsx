import { useEffect, useMemo, useState } from "react";
import { ActionIcon, Alert, Badge, Button, Card, Group, Modal, Stack, Text, TextInput, Title } from "@mantine/core";
import { IconAlertCircle, IconDownload, IconRefresh, IconSearch, IconTrash, IconX } from "@tabler/icons-react";

import { clearLogs, exportFailedCases, fetchLogs, type LogRow } from "../api";
import { LogCard } from "../components/LogCard";


export function LogsRoute() {
  const [rows, setRows] = useState<LogRow[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "blue" | "red"; message: string } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [clearModalOpen, setClearModalOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return rows;
    }
    return rows.filter((row) => {
      const haystack = [
        row.user,
        row.error,
        row.result,
        row.raw_output_summary,
        ...row.candidates,
      ].join(" ").toLowerCase();
      return haystack.includes(normalized);
    });
  }, [query, rows]);

  async function loadRows() {
    setState("loading");
    setError(null);
    try {
      const payload = await fetchLogs();
      setRows(payload.rows);
      setState("ready");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unknown error.");
      setState("error");
    }
  }

  useEffect(() => {
    void loadRows();
  }, []);

  async function handleExportFailedCases() {
    setIsExporting(true);
    setNotice(null);
    try {
      const payload = await exportFailedCases();
      setNotice({ tone: "blue", message: `${payload.rows_written} rows exported to ${payload.dataset.name}.` });
    } catch (exportError) {
      setNotice({ tone: "red", message: exportError instanceof Error ? exportError.message : "Unknown error." });
    } finally {
      setIsExporting(false);
    }
  }

  async function handleClearLogs() {
    setIsClearing(true);
    setNotice(null);
    try {
      const payload = await clearLogs();
      setRows([]);
      setQuery("");
      setClearModalOpen(false);
      setNotice({ tone: "blue", message: `${payload.rows_deleted} log rows deleted.` });
    } catch (clearError) {
      setNotice({ tone: "red", message: clearError instanceof Error ? clearError.message : "Unknown error." });
    } finally {
      setIsClearing(false);
    }
  }

  return (
    <Stack gap="lg">
      <Modal
        opened={clearModalOpen}
        onClose={() => setClearModalOpen(false)}
        title="Clear logs?"
        centered
      >
        <Stack>
          <Text size="sm" c="dimmed">
            This removes stored router log rows from the local log file. Export failed cases first if you want to keep them for dataset work.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setClearModalOpen(false)}>Cancel</Button>
            <Button color="red" loading={isClearing} leftSection={<IconTrash size={16} />} onClick={() => void handleClearLogs()}>
              Clear logs
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Logs</Title>
          <Text c="dimmed" size="sm">Routing incidents</Text>
        </div>
        <Group>
          <Badge variant="light">
            {filteredRows.length === rows.length ? `${rows.length} total` : `${filteredRows.length} / ${rows.length}`}
          </Badge>
          <Button variant="default" leftSection={<IconDownload size={16} />} loading={isExporting} onClick={() => void handleExportFailedCases()}>
            Export failed
          </Button>
          <Button
            variant="light"
            color="red"
            leftSection={<IconTrash size={16} />}
            disabled={rows.length === 0}
            onClick={() => setClearModalOpen(true)}
          >
            Clear
          </Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={() => void loadRows()}>
            Refresh
          </Button>
        </Group>
      </Group>

      {notice ? (
        <Alert color={notice.tone}>{notice.message}</Alert>
      ) : null}

      {state === "error" ? (
        <Alert color="red" title="Could not load logs" icon={<IconAlertCircle size={18} />}>
          {error}
        </Alert>
      ) : null}

      <Card>
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
          placeholder="Search logs"
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
        />
      </Card>

      {state === "loading" ? (
        <Card>
          <Text c="dimmed">Loading incidents...</Text>
        </Card>
      ) : null}

      {state === "ready" && filteredRows.length === 0 ? (
        <Card>
          <Text c="dimmed">No incidents.</Text>
        </Card>
      ) : null}

      {filteredRows.length > 0 ? (
        <Stack className="logs-list">
          {filteredRows.map((row, index) => (
            <LogCard key={`${row.user}-${index}`} row={row} />
          ))}
        </Stack>
      ) : null}
    </Stack>
  );
}
