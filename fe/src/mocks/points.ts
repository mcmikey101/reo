import { http, HttpResponse } from 'msw'

import { API_URL } from '../api/client'
import type { Point, PointInput } from '../api/points'
import { csvImportHandlers } from './csvImport'

const pointsUrl = `${API_URL}/points`
const storageKey = 'reo.mock.points'
const date = '2026-11-10T09:15:00Z'
const seed: Point[] = [
  { id: '3f2b9c1e-8a4d-4c6b-9f1a-2d7e5b8c0a11', name: 'Арбат', address: 'Москва, ул. Арбат, 24', category: 'Кофейня' },
  { id: 'a7c4e2d0-5b1f-4e8a-b3c9-6f0d2e4a8b17', name: 'Север', address: 'Москва, Ленинградское шоссе, 16', category: 'Кофейня' },
  { id: '39c9dfac-d182-4fbd-9da4-450a4ec00e11', name: 'Садовая', address: 'Москва, Садовая-Самотёчная ул., 8', category: 'Кофейня в ТЦ' },
].map((point) => ({ ...point, sources_count: 0, data_status: 'no_sources', created_at: date, updated_at: date }))

const normalize = (value: string) => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase('ru')
const notFound = () => HttpResponse.json(
  { error: { code: 'not_found', message: 'Точка не найдена', details: null } }, { status: 404 },
)

function validate(input: PointInput | Partial<PointInput>, creating: boolean) {
  const fields = []
  for (const [field, limit] of [['name', 120], ['address', 250], ['category', 60]] as const) {
    const value = input[field]
    if (value === undefined && !creating) continue
    if (field !== 'category' && !value) {
      fields.push({ field, code: 'blank', message: field === 'name' ? 'Укажите название' : 'Укажите адрес' })
    } else if (value && [...value].length > limit) {
      fields.push({ field, code: 'too_long', message: `Не больше ${limit} символов` })
    }
  }
  if (fields.length) {
    return HttpResponse.json({ error: { code: 'validation_error', message: 'Проверьте поля формы', details: { fields } } }, { status: 422 })
  }
}

export function pointHandlers(storage?: Storage, importStorage?: Storage) {
  const saved = storage?.getItem(storageKey)
  let points: Point[] = saved ? JSON.parse(saved) as Point[] : storage ? seed : []

  function update(next: Point[]) {
    points = next
    storage?.setItem(storageKey, JSON.stringify(next))
  }

  async function save(request: Request, existing?: Point) {
    const body = await request.json() as Partial<PointInput>
    const input = {
      name: body.name?.trim() ?? existing?.name ?? '',
      address: body.address?.trim() ?? existing?.address ?? '',
      category: body.category === undefined ? existing?.category ?? null : body.category?.trim() || null,
    }
    const validation = validate(input, !existing)
    if (validation) return validation

    if (new URL(request.url).searchParams.get('allow_duplicate') !== 'true') {
      const duplicate = points.find((point) => point.id !== existing?.id &&
        normalize(point.name) === normalize(input.name) && normalize(point.address) === normalize(input.address))
      if (duplicate) {
        const { id, name, address } = duplicate
        return HttpResponse.json({
          error: { code: 'possible_duplicate', message: 'Точка с таким названием и адресом уже есть', details: { existing_point: { id, name, address } } },
        }, { status: 409 })
      }
    }

    const now = new Date().toISOString()
    const point: Point = {
      id: existing?.id ?? crypto.randomUUID(),
      ...input,
      sources_count: existing?.sources_count ?? 0,
      data_status: existing?.data_status ?? 'no_sources',
      created_at: existing?.created_at ?? now,
      updated_at: now,
    }
    update(existing ? points.map((item) => item.id === point.id ? point : item) : [...points, point])
    return HttpResponse.json(point, { status: existing ? 200 : 201 })
  }

  return [
    ...csvImportHandlers((id) => points.some((point) => point.id === id), importStorage),
    http.get(pointsUrl, ({ request }) => {
      const params = new URL(request.url).searchParams
      const q = params.get('q')?.trim().toLocaleLowerCase('ru') ?? ''
      const limit = Number(params.get('limit') ?? 50)
      const offset = Number(params.get('offset') ?? 0)
      const filtered = points
        .filter(({ name, address }) => name.toLocaleLowerCase('ru').includes(q) || address.toLocaleLowerCase('ru').includes(q))
        .sort((a, b) => a.name.localeCompare(b.name, 'ru') || a.id.localeCompare(b.id))
      return HttpResponse.json({ items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset })
    }),
    http.get(`${pointsUrl}/:id`, ({ params }) => {
      const point = points.find(({ id }) => id === params.id)
      return point ? HttpResponse.json(point) : notFound()
    }),
    http.post(pointsUrl, ({ request }) => save(request)),
    http.patch(`${pointsUrl}/:id`, ({ params, request }) => {
      const point = points.find(({ id }) => id === params.id)
      return point ? save(request, point) : notFound()
    }),
    http.delete(`${pointsUrl}/:id`, ({ params }) => {
      const next = points.filter(({ id }) => id !== params.id)
      if (points.length === next.length) return notFound()
      update(next)
      return new HttpResponse(null, { status: 204 })
    }),
  ]
}
