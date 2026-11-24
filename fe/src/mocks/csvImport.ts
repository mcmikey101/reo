import { http, HttpResponse } from 'msw'

import { API_URL } from '../api/client'
import type { CsvImportResult } from '../api/csvImport'
import type { ImportAnalysis } from '../api/importAnalysis'
import type { Point } from '../api/points'

export const demoImportPoint: Point = {
  id: 'a0000000-0000-4000-8000-000000000201',
  name: 'Зерно на Тверской',
  address: 'Москва, ул. Тверская, 1',
  category: 'Кофейня',
  sources_count: 0,
  data_status: 'no_sources',
  created_at: '2026-11-20T09:00:00Z',
  updated_at: '2026-11-20T09:00:00Z',
}

export const demoImportResult: CsvImportResult = {
  import_id: 'e7d1cdba-8fca-4f94-b38d-59fb911d308a',
  source_id: '26ec26f7-7a38-4698-ae88-726c17bfe873',
  point_id: demoImportPoint.id,
  total: 4,
  imported: 3,
  duplicates: 0,
  rejected: 1,
  errors: [{
    row: 5,
    field: 'rating',
    code: 'invalid_rating',
    message: 'Оценка должна быть числом от 1 до 5 или пустой',
  }],
}

interface MockImport {
  pointId: string
  startedAt?: number
}

const importStorageKey = (importId: string) => `reo.mock.csv-import:${API_URL}:${importId}`

function readStoredImport(storage: Storage | undefined, importId: string): MockImport | undefined {
  try {
    const raw = storage?.getItem(importStorageKey(importId))
    if (!raw) return
    const entry = JSON.parse(raw) as Partial<MockImport> | null
    if (entry && typeof entry.pointId === 'string' &&
        (entry.startedAt === undefined || Number.isFinite(entry.startedAt))) {
      return { pointId: entry.pointId, startedAt: entry.startedAt }
    }
  } catch {
    // Повреждённая запись не считается импортом.
  }
}

function mockAnalysis(importId: string, startedAt?: number): ImportAnalysis {
  if (startedAt === undefined) return { import_id: importId, status: 'pending', result: null, error: null }
  if (Date.now() - startedAt < 2_500) return { import_id: importId, status: 'running', result: null, error: null }
  return {
    import_id: importId,
    status: 'done',
    result: { sentiment_counts: { positive: 1, neutral: 1, negative: 1 }, satisfaction_index: 58.3 },
    error: null,
  }
}

export function csvImportHandlers(hasPoint: (id: string) => boolean, storage?: Storage) {
  const imports = new Map<string, MockImport>()

  function rememberImport(importId: string, entry: MockImport) {
    imports.set(importId, entry)
    try {
      storage?.setItem(importStorageKey(importId), JSON.stringify(entry))
    } catch {
      // При недоступном хранилище мок работает до обновления страницы.
    }
  }

  function analysisResponse(importId: string, start: boolean) {
    const entry = imports.get(importId) ?? readStoredImport(storage, importId)
    if (!entry || !hasPoint(entry.pointId)) {
      return HttpResponse.json({ error: { code: 'not_found', message: 'Импорт не найден', details: null } }, { status: 404 })
    }
    if (start && entry.startedAt === undefined) {
      entry.startedAt = Date.now()
      rememberImport(importId, entry)
    }
    const analysis = mockAnalysis(importId, entry.startedAt)
    return HttpResponse.json(analysis, { status: start && analysis.status === 'running' ? 202 : 200 })
  }

  return [
    http.post(`${API_URL}/imports/csv`, async ({ request }) => {
      const body = await request.formData()
      const pointId = body.get('point_id')
      if (typeof pointId !== 'string' || !hasPoint(pointId)) {
        return HttpResponse.json({ error: { code: 'not_found', message: 'Точка не найдена', details: null } }, { status: 404 })
      }
      const file = body.get('file')
      if (!file || typeof file === 'string') {
        return HttpResponse.json({ error: { code: 'validation_error', message: 'Выберите CSV-файл', details: null } }, { status: 422 })
      }
      // Ответ из примера в docs/api-contract.md для просмотра штатного отчёта.
      const importId = crypto.randomUUID()
      rememberImport(importId, { pointId })
      return HttpResponse.json({ ...demoImportResult, point_id: pointId, import_id: importId }, { status: 201 })
    }),
    http.post<{ importId: string }>(`${API_URL}/imports/:importId/analysis`, ({ params }) =>
      analysisResponse(params.importId, true),
    ),
    http.get<{ importId: string }>(`${API_URL}/imports/:importId/analysis`, ({ params }) =>
      analysisResponse(params.importId, false),
    ),
  ]
}
