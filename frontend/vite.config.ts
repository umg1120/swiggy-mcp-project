import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `@/` alias, used by the @chaiui registry components (components.json).
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: Number(process.env.PORT) || 5173,
    // Lets peers reach the dev server through a temporary tunnel
    // (`cloudflared tunnel --url http://localhost:5173` or `ngrok http 5173`).
    // Vite rejects requests for hostnames it doesn't recognise otherwise.
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app'],
    proxy: {
      // FastAPI JSON API used by this app.
      '/api': 'http://localhost:8000',
      // Full-page OAuth redirect flow (Swiggy connect) -- must hit the
      // real backend, not be handled client-side.
      '/auth': 'http://localhost:8000',
    },
  },
})
