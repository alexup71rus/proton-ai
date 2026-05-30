import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MantineProvider, createTheme } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { App } from "./App";
import "./styles.css";

const theme = createTheme({
  primaryColor: "indigo",
  defaultRadius: "sm",
  fontFamily:
    'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  headings: {
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontWeight: "650",
  },
  components: {
    Card: {
      defaultProps: {
        withBorder: true,
        shadow: "none",
      },
    },
    Button: {
      defaultProps: {
        radius: "sm",
      },
    },
    ActionIcon: {
      defaultProps: {
        radius: "sm",
      },
    },
  },
});


ReactDOM.createRoot(document.getElementById("root")!).render(
  <MantineProvider theme={theme} defaultColorScheme="dark">
    <Notifications position="top-right" />
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </BrowserRouter>
  </MantineProvider>,
);
