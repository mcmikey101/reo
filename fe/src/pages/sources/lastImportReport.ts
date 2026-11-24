import { API_URL } from '../../api/client'
import { isImportResult } from '../../api/csvImport'
import type { CsvReport } from './CsvImportReport'

const storageKey = `reo.csv-import.last-report:${API_URL}`

export const lastImportReportKey = ['last-csv-import-report', API_URL] as const

export function readLastImportReport(): CsvReport | null {
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

export function saveLastImportReport(report: CsvReport) {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(report))
  } catch {
    // Удаляем предыдущий отчёт при переполнении, чтобы при обновлении не показать другой импорт.
    try { sessionStorage.removeItem(storageKey) } catch { /* Хранилище недоступно. */ }
  }
}
