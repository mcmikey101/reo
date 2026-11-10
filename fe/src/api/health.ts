import { useQuery } from '@tanstack/react-query'

import { ApiError, apiGet } from './client'

export type PartStatus = 'ok' | 'error'

/** Ответ GET /health бэкенда — docs/conventions.md, раздел 7 */
export interface HealthResponse {
  status: 'ok'
  db: PartStatus
  ml: PartStatus
}

/** Как часто опрашиваем /health, пока вкладка открыта */
export const HEALTH_POLL_MS = 15_000
const HEALTH_TIMEOUT_MS = 5_000

const isPartStatus = (value: unknown): value is PartStatus => value === 'ok' || value === 'error'

/** Проверяет формат ответа. Если он не совпадает с контрактом — ApiError с kind = 'parse'. */
export function parseHealth(body: unknown): HealthResponse {
  if (typeof body === 'object' && body !== null && 'status' in body && 'db' in body && 'ml' in body) {
    const { status, db, ml } = body
    if (status === 'ok' && isPartStatus(db) && isPartStatus(ml)) return { status, db, ml }
  }
  throw new ApiError('Ответ /health не совпадает с форматом из docs/conventions.md', { kind: 'parse' })
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return parseHealth(await apiGet('/health', { signal, timeoutMs: HEALTH_TIMEOUT_MS }))
}

/** Состояние API, БД и ML с периодическим опросом */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: HEALTH_POLL_MS,
    // Не повторяем сразу: иначе красный цвет появится только через несколько попыток.
    // Повтор — следующий опрос.
    retry: false,
  })
}
