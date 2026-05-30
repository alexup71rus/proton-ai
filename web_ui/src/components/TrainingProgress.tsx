import { Alert, Badge, Card, Group, Progress, SimpleGrid, Stack, Text, Title } from "@mantine/core";

import type { TrainingStatus } from "../api";
import { formatTrainingStatusLabel } from "../trainingStatus";


export interface TrainingProgressProps {
  status: TrainingStatus | null;
}


function formatMetric(value: number | null | undefined): string {
  if (value == null) {
    return "-";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}


function formatRatio(hit: number, total: number): string {
  if (total <= 0) {
    return "-";
  }
  const rate = (hit / total) * 100;
  return `${hit} / ${total} (${rate.toFixed(1)}%)`;
}


function buildSparkline(values: number[]): string | null {
  if (values.length < 2) {
    return null;
  }

  const width = 1000;
  const height = 180;
  const padding = 8;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / Math.max(values.length - 1, 1);

  return values
    .map((value, index) => {
      const x = index * step;
      const normalized = (value - min) / span;
      const y = height - padding - normalized * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");
}


function metricCard(label: string, value: string) {
  return (
    <Card bg="dark.7">
      <Text size="xs" tt="uppercase" c="dimmed" fw={700}>{label}</Text>
      <div className="metric-value">{value}</div>
    </Card>
  );
}


export function TrainingProgress({ status }: TrainingProgressProps) {
  const lossHistory = status?.loss_history ?? [];
  const lossHistoryTotal = status?.loss_history_total ?? lossHistory.length;
  const metrics = status?.metrics ?? {};
  const sparkline = status ? buildSparkline(lossHistory) : null;
  const invalidCount = Math.max((status?.eval_total ?? 0) - (status?.eval_valid ?? 0), 0);
  const hasRunState = Boolean(status && status.status !== "idle");
  const runStatus = hasRunState && status ? status : null;
  const progressValue = runStatus && runStatus.total_steps > 0
    ? Math.min(100, (runStatus.current_step / runStatus.total_steps) * 100)
    : 0;

  return (
    <Card>
      <Stack>
        <Group justify="space-between">
          <Title order={3}>Training run</Title>
          {hasRunState ? (
            <Badge color={status?.status === "failed" ? "red" : status?.status === "running" ? "blue" : "green"}>
              {formatTrainingStatusLabel(status?.status)}
            </Badge>
          ) : null}
        </Group>

        {!runStatus ? (
          <Card bg="dark.7">
            <Text c="dimmed">No training state yet.</Text>
          </Card>
        ) : (
          <>
            <Progress value={progressValue} />

            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              {metricCard("Epoch", `${runStatus.current_epoch ?? 0} / ${runStatus.total_epochs ?? 0}`)}
              {metricCard("Step", `${runStatus.current_step ?? 0} / ${runStatus.total_steps ?? 0}`)}
              {metricCard("Loss", formatMetric(runStatus.loss))}
              {metricCard("Checkpoint", runStatus.checkpoint_path ? "Ready" : "Pending")}
            </SimpleGrid>

            <Card bg="dark.7">
              <Group justify="space-between" mb="xs">
                <Text fw={650}>Loss curve</Text>
                <Text size="sm" c="dimmed">
                  {lossHistory.length === lossHistoryTotal
                    ? `${lossHistory.length} samples`
                    : `${lossHistory.length} shown / ${lossHistoryTotal} total`}
                </Text>
              </Group>
              {sparkline ? (
                <svg viewBox="0 0 1000 180" preserveAspectRatio="none" className="loss-chart" role="img" aria-label="Loss history">
                  <polyline fill="none" stroke="currentColor" strokeWidth="4" points={sparkline} />
                </svg>
              ) : (
                <Text size="sm" c="dimmed">Waiting for loss samples.</Text>
              )}
            </Card>

            <SimpleGrid cols={{ base: 1, md: 2 }}>
              <Card bg="dark.7">
                <Text fw={650} mb="sm">Evaluation</Text>
                {runStatus.eval_total === 0 ? (
                  <Text size="sm" c="dimmed">No evaluation yet.</Text>
                ) : (
                  <Stack gap={6}>
                    <Text size="sm">Exact match: {formatRatio(runStatus.eval_exact, runStatus.eval_total)}</Text>
                    <Text size="sm">Valid output: {formatRatio(runStatus.eval_valid, runStatus.eval_total)}</Text>
                    <Text size="sm">Positive rows: {formatRatio(runStatus.eval_positive_exact, runStatus.eval_positive_total)}</Text>
                    <Text size="sm">Fallback rows: {formatRatio(runStatus.eval_fallback_exact, runStatus.eval_fallback_total)}</Text>
                    <Text size="sm">Invalid outputs: {formatMetric(invalidCount)}</Text>
                  </Stack>
                )}
              </Card>

              <Card bg="dark.7">
                <Text fw={650} mb="sm">Metrics</Text>
                {Object.keys(metrics).length === 0 ? (
                  <Text size="sm" c="dimmed">No metrics.</Text>
                ) : (
                  <Stack gap={6}>
                    {Object.entries(metrics).map(([name, value]) => (
                      <Text key={name} size="sm">{name}: {formatMetric(value)}</Text>
                    ))}
                  </Stack>
                )}
              </Card>
            </SimpleGrid>

            {runStatus.error ? (
              <Alert color="red" title="Training failed">{runStatus.error}</Alert>
            ) : null}
          </>
        )}
      </Stack>
    </Card>
  );
}
