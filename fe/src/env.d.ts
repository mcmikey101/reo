// Переменные окружения фронтенда (docs/conventions.md, раздел 3)
interface ImportMetaEnv {
  /** Адрес API бэкенда. По умолчанию http://localhost:8000 */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
