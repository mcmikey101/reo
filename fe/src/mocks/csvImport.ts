import { http, HttpResponse } from 'msw'

import { API_URL } from '../api/client'
import type { CsvImportResult } from '../api/csvImport'

export const demoImportPoint = {
  id: 'a0000000-0000-4000-8000-000000000201',
  name: 'Зерно на Тверской',
  address: 'Москва, ул. Тверская, 1',
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

export const csvImportHandlers = [
  http.get(`${API_URL}/points`, () =>
    HttpResponse.json({ items: [demoImportPoint], total: 1, limit: 50, offset: 0 }),
  ),
  http.post(`${API_URL}/imports/csv`, async ({ request }) => {
    const body = await request.formData()
    if (body.get('point_id') !== demoImportPoint.id) {
      return HttpResponse.json({ error: { code: 'not_found', message: 'Точка не найдена', details: null } }, { status: 404 })
    }
    const file = body.get('file')
    if (!file || typeof file === 'string') {
      return HttpResponse.json({ error: { code: 'validation_error', message: 'Выберите CSV-файл', details: null } }, { status: 422 })
    }
    // Ответ из примера в docs/api-contract.md для просмотра штатного отчёта.
    return HttpResponse.json(demoImportResult, { status: 201 })
  }),
]
