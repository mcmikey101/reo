/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { msw } from 'msw/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    // Режим моков (npm run dev:mock): плагин отдаёт скрипт service worker MSW.
    // В обычном запуске и в сборке его нет.
    mode === 'mock' && msw({ mode: 'worker-only' }),
  ],
  server: {
    // CORS бэкенда разрешает только http://localhost:5173 (docs/conventions.md),
    // поэтому на другой порт не переходим, а падаем с понятной ошибкой.
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
}))
