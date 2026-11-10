import { QueryClient } from '@tanstack/react-query'

/** Кеш серверных данных (TanStack Query). Один на приложение, в тестах — новый на каждый тест. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
      },
    },
  })
}
