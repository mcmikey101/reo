import { skipToken, useQuery, type QueryClient } from '@tanstack/react-query'

import { API_URL } from '../api/client'
import { isImportResult, type CsvImportResult } from '../api/csvImport'

export interface CsvReport {
  result: CsvImportResult
  pointName: string
  fileName: string
}

const storageKey = `reo.csv-import.last-report:${API_URL}`
const lastImportReportKey = ['last-csv-import-report', API_URL] as const

function readStoredReport(): CsvReport | null {
  try {
    const raw = sessionStorage.getItem(storageKey)
    if (!raw) return null
    const report = JSON.parse(raw) as Partial<CsvReport> | null
    if (report && typeof report.pointName === 'string' && typeof report.fileName === 'string' &&
        isImportResult(report.result)) {
      return { pointName: report.pointName, fileName: report.fileName, result: report.result }
    }
  } catch {
    // Хранилище может быть недоступно или содержать устаревший отчёт.
  }
  return null
}

export function useLastImportReport() {
  return useQuery<CsvReport | null>({
    queryKey: lastImportReportKey,
    queryFn: skipToken,
    initialData: readStoredReport,
  })
}

export function saveLastImportReport(client: QueryClient, report: CsvReport | null) {
  client.setQueryData(lastImportReportKey, report)
  try {
    if (report) sessionStorage.setItem(storageKey, JSON.stringify(report))
    else sessionStorage.removeItem(storageKey)
  } catch {
    // Удаляем предыдущий отчёт при переполнении, чтобы при обновлении не показать другой импорт.
    try { sessionStorage.removeItem(storageKey) } catch { /* Хранилище недоступно. */ }
  }
}

export function clearLastImportReport(client: QueryClient, field: 'import_id' | 'point_id', id: string) {
  const cached = client.getQueryData<CsvReport | null>(lastImportReportKey)
  const report = cached === undefined ? readStoredReport() : cached
  if (report?.result[field] === id) saveLastImportReport(client, null)
}
