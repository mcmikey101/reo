import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { clearLastImportReport } from '../state/lastImportReport'
import { ApiError, apiGet, apiRequest } from './client'

interface AnalysisResult {
  sentiment_counts: { positive: number; neutral: number; negative: number }
  satisfaction_index: number | null
}

interface AnalysisError {
  code: 'ml_error' | 'analysis_failed'
  message: string
}

export type ImportAnalysis = { import_id: string } & (
  | { status: 'pending' | 'running'; result: null; error: null }
  | { status: 'done'; result: AnalysisResult; error: null }
  | { status: 'error'; result: AnalysisResult; error: AnalysisError }
)

const POLL_INTERVAL_MS = 2_000

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isResult(value: unknown): value is AnalysisResult {
  if (!value || typeof value !== 'object') return false
  const { sentiment_counts: counts, satisfaction_index: index } = value as Partial<AnalysisResult>
  return !!counts && isCount(counts.positive) && isCount(counts.neutral) && isCount(counts.negative) &&
    (index === null || (typeof index === 'number' && Number.isFinite(index) && index >= 0 && index <= 100))
}

function isAnalysisError(value: unknown): value is AnalysisError {
  if (!value || typeof value !== 'object') return false
  const { code, message } = value as Partial<AnalysisError>
  return (code === 'ml_error' || code === 'analysis_failed') && typeof message === 'string'
}

function isAnalysis(value: unknown, importId: string): value is ImportAnalysis {
  if (!value || typeof value !== 'object') return false
  const { import_id, status, result, error } = value as Partial<ImportAnalysis>
  if (import_id !== importId) return false
  switch (status) {
    case 'pending':
    case 'running':
      return result === null && error === null
    case 'done':
      return isResult(result) && error === null
    case 'error':
      return isResult(result) && isAnalysisError(error)
    default:
      return false
  }
}

function parseAnalysis(value: unknown, importId: string): ImportAnalysis {
  if (!isAnalysis(value, importId)) {
    throw new ApiError('API вернул ответ анализа в неожиданном формате', { kind: 'parse' })
  }
  return value
}

/** POST запускает анализ, GET проверяет его состояние без запуска ML. */
export function useImportAnalysis(importId: string, restored: boolean) {
  const client = useQueryClient()
  const queryKey = ['import-analysis', importId] as const
  const path = `/imports/${encodeURIComponent(importId)}/analysis`

  const status = useQuery({
    queryKey,
    queryFn: async ({ signal }) => parseAnalysis(await apiGet(path, { signal }), importId),
    enabled: (query) => query.state.data?.status === 'running' || (restored && !query.state.data),
    refetchInterval: (query) =>
      query.state.data?.status === 'running' && query.state.status !== 'error' ? POLL_INTERVAL_MS : false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  })

  const start = useMutation({
    mutationFn: async () => parseAnalysis(await apiRequest(path, { method: 'POST' }), importId),
    onSuccess: async (data) => {
      // GET, начатый при возврате к отчёту, может принести статус до запуска.
      await client.cancelQueries({ queryKey, exact: true })
      client.setQueryData(queryKey, data)
    },
    retry: false,
  })

  const error = status.error ?? start.error
  useEffect(() => {
    if (error instanceof ApiError && error.status === 404) {
      clearLastImportReport(client, 'import_id', importId)
    }
  }, [client, error, importId])

  return { status, start }
}
