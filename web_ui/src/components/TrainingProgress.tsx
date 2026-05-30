import { useMemo, useState, type MouseEvent } from "react";
import { Alert, Badge, Card, Group, Progress, SimpleGrid, Stack, Text, Title } from "@mantine/core";

import type { TrainingStatus } from "../api";
import { formatTrainingStatusLabel } from "../trainingStatus";


export interface TrainingProgressProps {
  status: TrainingStatus | null;
}


const LOSS_CHART_WIDTH = 1000;
const LOSS_CHART_HEIGHT = 220;
const LOSS_CHART_PADDING = 14;


type LossChartPoint = {
  index: number;
  value: number;
  x: number;
  y: number;
};


type LossChartData = {
  points: LossChartPoint[];
  polyline: string;
};


function formatMetric(value: number | null | undefined): string {
  if (value == null) {
    return "-";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}


function formatLossTooltip(value: number): string {
  if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) {
    return value.toExponential(3);
  }
  return value.toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
}


function formatRatio(hit: number, total: number): string {
  if (total <= 0) {
    return "-";
  }
  const rate = (hit / total) * 100;
  return `${hit} / ${total} (${rate.toFixed(1)}%)`;
}


function buildLossChart(values: number[]): LossChartData | null {
  if (values.length < 2) {
    return null;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = LOSS_CHART_WIDTH / Math.max(values.length - 1, 1);

  const points = values
    .map<LossChartPoint>((value, index) => {
      const x = index * step;
      const normalized = (value - min) / span;
      const y = LOSS_CHART_HEIGHT - LOSS_CHART_PADDING - normalized * (LOSS_CHART_HEIGHT - LOSS_CHART_PADDING * 2);
      return { index, value, x, y };
    });

  return {
    points,
    polyline: points.map((point) => `${point.x},${point.y}`).join(" "),
  };
}


function buildEpochSeparators(totalEpochs: number): Array<{ epoch: number; x: number }> {
  if (totalEpochs <= 1) {
    return [];
  }
  return Array.from({ length: totalEpochs - 1 }, (_, index) => ({
    epoch: index + 2,
    x: LOSS_CHART_WIDTH * ((index + 1) / totalEpochs),
  }));
}


function estimateEpoch(pointIndex: number, pointCount: number, totalEpochs: number): number | null {
  if (totalEpochs <= 1 || pointCount <= 1) {
    return null;
  }
  const ratio = pointIndex / Math.max(pointCount - 1, 1);
  return Math.min(totalEpochs, Math.floor(ratio * totalEpochs) + 1);
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
  const [hoveredLossIndex, setHoveredLossIndex] = useState<number | null>(null);
  const lossHistory = status?.loss_history ?? [];
  const lossHistoryTotal = status?.loss_history_total ?? lossHistory.length;
  const metrics = status?.metrics ?? {};
  const lossChart = useMemo(() => (status ? buildLossChart(lossHistory) : null), [lossHistory, status]);
  const invalidCount = Math.max((status?.eval_total ?? 0) - (status?.eval_valid ?? 0), 0);
  const hasRunState = Boolean(status && status.status !== "idle");
  const runStatus = hasRunState && status ? status : null;
  const progressValue = runStatus && runStatus.total_steps > 0
    ? Math.min(100, (runStatus.current_step / runStatus.total_steps) * 100)
    : 0;
  const activeLossPoint = hoveredLossIndex != null ? lossChart?.points[hoveredLossIndex] ?? null : null;
  const epochSeparators = buildEpochSeparators(runStatus?.total_epochs ?? 0);
  const activeEpoch = activeLossPoint
    ? estimateEpoch(activeLossPoint.index, lossChart?.points.length ?? 0, runStatus?.total_epochs ?? 0)
    : null;

  function handleLossChartMove(event: MouseEvent<SVGSVGElement>) {
    if (!lossChart?.points.length) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    setHoveredLossIndex(Math.round(ratio * (lossChart.points.length - 1)));
  }

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
              {lossChart ? (
                <div className="loss-chart-wrap">
                  <svg
                    viewBox={`0 0 ${LOSS_CHART_WIDTH} ${LOSS_CHART_HEIGHT}`}
                    preserveAspectRatio="none"
                    className="loss-chart"
                    role="img"
                    aria-label="Loss history"
                    onMouseMove={handleLossChartMove}
                    onMouseLeave={() => setHoveredLossIndex(null)}
                  >
                    {epochSeparators.map((separator) => (
                      <g key={separator.epoch}>
                        <line
                          className="loss-chart__epoch-line"
                          x1={separator.x}
                          x2={separator.x}
                          y1={0}
                          y2={LOSS_CHART_HEIGHT}
                        />
                        <text className="loss-chart__epoch-label" x={separator.x + 8} y={18}>
                          E{separator.epoch}
                        </text>
                      </g>
                    ))}
                    <polyline className="loss-chart__line" fill="none" points={lossChart.polyline} />
                    {activeLossPoint ? (
                      <>
                        <line
                          className="loss-chart__hover-line"
                          x1={activeLossPoint.x}
                          x2={activeLossPoint.x}
                          y1={0}
                          y2={LOSS_CHART_HEIGHT}
                        />
                        <circle className="loss-chart__hover-dot" cx={activeLossPoint.x} cy={activeLossPoint.y} r={7} />
                      </>
                    ) : null}
                  </svg>
                  {activeLossPoint ? (
                    <div
                      className="loss-chart-tooltip"
                      style={{
                        left: `${Math.min(92, Math.max(8, (activeLossPoint.x / LOSS_CHART_WIDTH) * 100))}%`,
                        top: `${Math.min(88, Math.max(12, (activeLossPoint.y / LOSS_CHART_HEIGHT) * 100))}%`,
                      }}
                    >
                      <div className="loss-chart-tooltip__value">Loss {formatLossTooltip(activeLossPoint.value)}</div>
                      <div>
                        Point {activeLossPoint.index + 1} / {lossHistory.length}
                        {lossHistory.length !== lossHistoryTotal ? ` shown, ${lossHistoryTotal} total` : ""}
                      </div>
                      {activeEpoch ? <div>Epoch {activeEpoch}</div> : null}
                    </div>
                  ) : null}
                </div>
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
