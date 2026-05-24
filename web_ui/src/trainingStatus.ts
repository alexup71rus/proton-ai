import type { TrainingStatus } from "./api";


export type TrainingRunState = TrainingStatus["status"] | null | undefined;


export function formatTrainingStatusLabel(status: TrainingRunState): string {
  switch (status) {
    case "running":
      return "running";
    case "completed":
    case "success":
      return "complete";
    case "failed":
      return "failed";
    case "idle":
    case undefined:
    case null:
      return "no run yet";
    default:
      return status.split("_").join(" ");
  }
}