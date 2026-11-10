// Моки API по контрактам из docs/. Работают в режиме npm run dev:mock и в тестах.
import { http, HttpResponse } from 'msw'

import { API_URL } from '../api/client'
import type { HealthResponse } from '../api/health'

export const healthyResponse: HealthResponse = { status: 'ok', db: 'ok', ml: 'ok' }

/**
 * Состояние /health в режиме моков задаётся параметром в адресе страницы:
 * ?health=db-error | ml-error | down. Без параметра всё работает.
 */
function healthScenario(): string | null {
  if (typeof window === 'undefined') return null
  return new URLSearchParams(window.location.search).get('health')
}

export const handlers = [
  http.get(`${API_URL}/health`, () => {
    switch (healthScenario()) {
      case 'down':
        return HttpResponse.error()
      case 'db-error':
        return HttpResponse.json<HealthResponse>({ ...healthyResponse, db: 'error' })
      case 'ml-error':
        return HttpResponse.json<HealthResponse>({ ...healthyResponse, ml: 'error' })
      default:
        return HttpResponse.json(healthyResponse)
    }
  }),
]
