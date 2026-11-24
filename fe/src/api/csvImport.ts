import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiRequest } from './client'
import { pointsKey } from './points'

export const MAX_CSV_BYTES = 10 * 1024 * 1024

interface CsvRowError {
  row: number
  field: string | null
  code: string
  message: string
}

export interface CsvImportResult {
  import_id: string
  point_id: string
  source_id: string
  total: number
  imported: number
  duplicates: number
  rejected: number
  errors: CsvRowError[]
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isRowError(value: unknown): value is CsvRowError {
  if (!value || typeof value !== 'object') return false
  const { row, field, code, message } = value as Partial<CsvRowError>
  return isCount(row) && row > 0 && (field === null || typeof field === 'string') &&
    typeof code === 'string' && typeof message === 'string'
}

function isImportResult(value: unknown): value is CsvImportResult {
  if (!value || typeof value !== 'object') return false
  const { import_id, point_id, source_id, total, imported, duplicates, rejected, errors } = value as Partial<CsvImportResult>
  return typeof import_id === 'string' && import_id.length > 0 &&
    typeof point_id === 'string' && typeof source_id === 'string' &&
    isCount(total) && isCount(imported) && isCount(duplicates) && isCount(rejected) &&
    total === imported + duplicates + rejected &&
    Array.isArray(errors) && errors.length === rejected && errors.every(isRowError)
}

export function useCsvImport() {
  const client = useQueryClient()
  return useMutation({
    retry: false,
    mutationFn: async ({ pointId, file }: { pointId: string; file: File }) => {
      const body = new FormData()
      body.set('point_id', pointId)
      body.set('file', file)
      const result = await apiRequest('/imports/csv', { method: 'POST', body, timeoutMs: 60_000 })
      if (!isImportResult(result)) {
        throw new ApiError('API вернул отчёт импорта в неожиданном формате', { kind: 'parse' })
      }
      return result
    },
    onSuccess: () => { void client.invalidateQueries({ queryKey: pointsKey }) },
  })
}
