// HTTP-клиент API бэкенда. Общие правила API — docs/api-contract.md, раздел 1.

const DEFAULT_API_URL = 'http://localhost:8000'
const DEFAULT_TIMEOUT_MS = 10_000

/** Адрес API без «/» в конце: VITE_API_URL или http://localhost:8000 */
export const API_URL = (import.meta.env.VITE_API_URL?.trim() || DEFAULT_API_URL).replace(/\/+$/, '')

/**
 * Что пошло не так:
 * - network — API не ответил: сервис не запущен, нет сети, запрет CORS;
 * - timeout — API не уложился во время ожидания;
 * - http — ответ 4xx или 5xx;
 * - parse — ответ не JSON или не того формата.
 */
export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'parse'

interface ApiErrorInit {
  kind: ApiErrorKind
  status?: number
  code?: string
  details?: unknown
  cause?: unknown
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  /** HTTP-статус, если kind = 'http' */
  readonly status?: number
  /** Машинный код из тела ошибки: validation_error, not_found и т. д. */
  readonly code?: string
  /** Подробности из тела ошибки, например поля формы */
  readonly details?: unknown

  constructor(message: string, init: ApiErrorInit) {
    super(message, { cause: init.cause })
    this.name = 'ApiError'
    this.kind = init.kind
    this.status = init.status
    this.code = init.code
    this.details = init.details
  }
}

interface RequestOptions {
  /** Сигнал отмены, например от TanStack Query */
  signal?: AbortSignal
  timeoutMs?: number
}

/** GET-запрос к API. Возвращает разобранный JSON или бросает ApiError. */
export async function apiGet(path: string, options: RequestOptions = {}): Promise<unknown> {
  const timeout = AbortSignal.timeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(API_URL + path, {
      headers: { Accept: 'application/json' },
      signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout,
    })
  } catch (cause) {
    if (timeout.aborted) throw new ApiError('API не ответил вовремя', { kind: 'timeout', cause })
    throw new ApiError('API недоступен', { kind: 'network', cause })
  }

  if (!response.ok) throw await toHttpError(response)

  try {
    return await response.json()
  } catch (cause) {
    throw new ApiError('API вернул ответ не в формате JSON', { kind: 'parse', cause })
  }
}

/** Тело ошибки API: {"error": {"code", "message", "details"}} — docs/api-contract.md, раздел 1.5 */
interface ErrorBody {
  error: { code: string; message: string; details: unknown }
}

function isErrorBody(body: unknown): body is ErrorBody {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false
  const error = body.error
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof error.code === 'string' &&
    'message' in error &&
    typeof error.message === 'string'
  )
}

async function toHttpError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // Тело не JSON — сообщим только статус
  }
  if (isErrorBody(body)) {
    return new ApiError(body.error.message, {
      kind: 'http',
      status: response.status,
      code: body.error.code,
      details: body.error.details,
    })
  }
  return new ApiError(`API ответил ошибкой ${response.status}`, { kind: 'http', status: response.status })
}
