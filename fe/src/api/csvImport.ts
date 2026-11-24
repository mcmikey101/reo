import { useInfiniteQuery, useMutation } from '@tanstack/react-query'

import { ApiError, apiGet, apiRequest } from './client'

export const MAX_CSV_BYTES = 10 * 1024 * 1024

interface ImportPoint {
  id: string
  name: string
  address: string
}

interface ImportPointsPage {
  items: ImportPoint[]
  total: number
  limit: number
  offset: number
}

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

function isImportPoint(value: unknown): value is ImportPoint {
  if (!value || typeof value !== 'object') return false
  const { id, name, address } = value as Partial<ImportPoint>
  return typeof id === 'string' && typeof name === 'string' && typeof address === 'string'
}

export function useImportPoints() {
  return useInfiniteQuery({
    queryKey: ['points', 'csv-import'],
    initialPageParam: 0,
    queryFn: async ({ signal, pageParam }) => {
      const result = await apiGet(`/points?limit=50&offset=${pageParam}`, { signal })
      if (result && typeof result === 'object') {
        const { items, total, limit, offset } = result as Partial<ImportPointsPage>
        if (Array.isArray(items) && items.every(isImportPoint) &&
            isCount(total) && isCount(limit) && limit > 0 && isCount(offset)) {
          return { items, total, limit, offset }
        }
      }
      throw new ApiError('API вернул список точек в неожиданном формате', { kind: 'parse' })
    },
    getNextPageParam: ({ items, offset, limit, total }) =>
      items.length && offset + limit < total ? offset + limit : undefined,
    retry: false,
  })
}

function isRowError(value: unknown): value is CsvRowError {
  if (!value || typeof value !== 'object') return false
  const { row, field, code, message } = value as Partial<CsvRowError>
  return isCount(row) && row > 0 && (field === null || typeof field === 'string') &&
    typeof code === 'string' && typeof message === 'string'
}

export function isImportResult(value: unknown): value is CsvImportResult {
  if (!value || typeof value !== 'object') return false
  const { import_id, point_id, source_id, total, imported, duplicates, rejected, errors } = value as Partial<CsvImportResult>
  return typeof import_id === 'string' && import_id.length > 0 &&
    typeof point_id === 'string' && typeof source_id === 'string' &&
    isCount(total) && isCount(imported) && isCount(duplicates) && isCount(rejected) &&
    total === imported + duplicates + rejected &&
    Array.isArray(errors) && errors.length === rejected && errors.every(isRowError)
}

export function useCsvImport() {
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
  })
}
