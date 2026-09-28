import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Явно IPv4: иначе Node может поднять сервер только на ::1, и часть браузеров не достучится.
  server: { host: "127.0.0.1", port: 5173, strictPort: true },
});
