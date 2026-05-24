import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DatasetTrainingRoute } from "./routes/DatasetTraining";
import { LogsRoute } from "./routes/Logs";
import { TestRoute } from "./routes/Test";
import { ToolsRoute } from "./routes/Tools";


const navItems = [
  {
    to: "/",
    label: "Tools",
    step: "01",
    description: "Define the registry and keep the source of truth clean.",
  },
  {
    to: "/dataset-training",
    label: "Dataset + Training",
    step: "02",
    description: "Manage dataset assets, then train from a validated file.",
  },
  {
    to: "/test",
    label: "Test",
    step: "03",
    description: "Check routing results without drowning in internals.",
  },
  {
    to: "/logs",
    label: "Logs",
    step: "04",
    description: "Turn failures into the next improvement loop.",
  },
];


export function App() {
  return (
    <AppShell navItems={navItems}>
      <Routes>
        <Route path="/" element={<ToolsRoute />} />
        <Route path="/dataset-training" element={<DatasetTrainingRoute />} />
        <Route path="/test" element={<TestRoute />} />
        <Route path="/logs" element={<LogsRoute />} />
        <Route path="/Tools" element={<Navigate to="/" replace />} />
        <Route path="/Dataset_Training" element={<Navigate to="/dataset-training" replace />} />
        <Route path="/Test" element={<Navigate to="/test" replace />} />
        <Route path="/Logs" element={<Navigate to="/logs" replace />} />
      </Routes>
    </AppShell>
  );
}
