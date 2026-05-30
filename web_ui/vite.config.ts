import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";


export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          mantine: ["@mantine/core", "@mantine/hooks", "@mantine/notifications"],
          icons: ["@tabler/icons-react"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  server: {
    port: 8501,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8100",
    },
  },
});
