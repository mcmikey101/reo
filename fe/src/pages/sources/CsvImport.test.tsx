import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { API_URL } from '../../api/client'
import { demoImportPoint, demoImportResult } from '../../mocks/csvImport'
import { server } from '../../mocks/node'
import { renderApp } from '../../test/render'

const csv = 'date,text,rating\n2026-11-20,Хороший кофе,5'

async function openImport() {
  const user = userEvent.setup()
  renderApp('/sources')
  await user.click(await screen.findByRole('button', { name: 'Импорт CSV' }))
  const dialog = within(screen.getByRole('dialog', { name: 'Импорт отзывов из CSV' }))
  return { user, dialog }
}

describe('Импорт CSV', () => {
  beforeAll(() => {
    // jsdom не реализует императивное открытие нативного <dialog>.
    HTMLDialogElement.prototype.showModal ??= function () { this.open = true }
    HTMLDialogElement.prototype.close ??= function () { this.open = false }
  })

  beforeEach(() => {
    server.use(http.get(`${API_URL}/points`, () =>
      HttpResponse.json({ items: [demoImportPoint], total: 1, limit: 50, offset: 0 }),
    ))
  })

  it('отправляет выбранную точку и файл одним multipart-запросом и показывает ошибки строк', async () => {
    server.use(http.post(`${API_URL}/imports/csv`, () =>
      HttpResponse.json(demoImportResult, { status: 201 }),
    ))
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const file = new File([csv], 'reviews.csv', { type: 'text/csv' })
    try {
      const { user, dialog } = await openImport()
      expect(dialog.getByText(/date,text,rating/)).toBeInTheDocument()
      expect(dialog.getByRole('button', { name: 'Импортировать' })).toBeDisabled()
      await dialog.findByRole('option', { name: /Зерно на Тверской/ })
      await user.selectOptions(dialog.getByRole('combobox'), demoImportPoint.id)
      await user.upload(dialog.getByLabelText('CSV-файл'), file)
      await user.click(dialog.getByRole('button', { name: 'Импортировать' }))

      const report = await screen.findByRole('region', { name: 'Импорт завершён' })
      const requests = fetchSpy.mock.calls.filter(([url]) => url === `${API_URL}/imports/csv`)
      expect(requests).toHaveLength(1)
      const options = requests[0]?.[1]
      expect(options?.method).toBe('POST')
      expect(new Headers(options?.headers).has('Content-Type')).toBe(false)
      expect(options?.body).toBeInstanceOf(FormData)
      const body = options?.body as FormData
      expect(body.get('point_id')).toBe(demoImportPoint.id)
      expect(body.get('file')).toBe(file)
      expect(within(report).getByText('Добавлено').nextElementSibling).toHaveTextContent('3')
      expect(within(report).getByRole('row', { name: '5 Оценка должна быть числом от 1 до 5 или пустой' })).toBeInTheDocument()
    } finally {
      fetchSpy.mockRestore()
    }
  })

  it('показывает серверную ошибку и сохраняет точку и файл для повторной попытки', async () => {
    server.use(http.post(`${API_URL}/imports/csv`, () =>
      HttpResponse.json({
        error: { code: 'invalid_csv', message: 'Заголовок должен быть date,text,rating', details: { row: 1 } },
      }, { status: 422 }),
    ))
    const { user, dialog } = await openImport()
    await dialog.findByRole('option', { name: /Зерно на Тверской/ })
    await user.selectOptions(dialog.getByRole('combobox'), demoImportPoint.id)
    await user.upload(dialog.getByLabelText('CSV-файл'), new File(['bad'], 'reviews.csv', { type: 'text/csv' }))
    await user.click(dialog.getByRole('button', { name: 'Импортировать' }))

    expect(await dialog.findByRole('alert')).toHaveTextContent('Заголовок должен быть date,text,rating')
    expect(dialog.getByRole('combobox')).toHaveValue(demoImportPoint.id)
    expect(dialog.getByText('reviews.csv')).toBeInTheDocument()
    expect(dialog.getByRole('button', { name: 'Импортировать' })).toBeEnabled()
  })

  it('позволяет выбрать точку со следующей страницы и показать отчёт с нулём новых отзывов', async () => {
    const nextPoint = { ...demoImportPoint, id: 'a0000000-0000-4000-8000-000000000202', name: 'Зерно на Арбате' }
    server.use(
      http.get(`${API_URL}/points`, ({ request }) => {
        const offset = Number(new URL(request.url).searchParams.get('offset'))
        return HttpResponse.json({ items: [offset ? nextPoint : demoImportPoint], total: 2, limit: 1, offset })
      }),
      http.post(`${API_URL}/imports/csv`, () =>
        HttpResponse.json({ ...demoImportResult, point_id: nextPoint.id, imported: 0, duplicates: 3 }, { status: 201 }),
      ),
    )
    const { user, dialog } = await openImport()
    await user.click(await dialog.findByRole('button', { name: 'Показать ещё точки' }))
    await dialog.findByRole('option', { name: /Зерно на Арбате/ })
    await user.selectOptions(dialog.getByRole('combobox'), nextPoint.id)
    await user.upload(dialog.getByLabelText('CSV-файл'), new File([csv], 'reviews.csv', { type: 'text/csv' }))
    await user.click(dialog.getByRole('button', { name: 'Импортировать' }))

    const report = await screen.findByRole('region', { name: 'Нет новых отзывов' })
    expect(within(report).getByText('Дубли').nextElementSibling).toHaveTextContent('3')
  })

  it('подсказывает, где добавить точку, если список пуст', async () => {
    server.use(http.get(`${API_URL}/points`, () =>
      HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
    ))
    const { dialog } = await openImport()
    expect(await dialog.findByRole('link', { name: '«Точки»' })).toHaveAttribute('href', '/points')
    expect(dialog.getByRole('button', { name: 'Импортировать' })).toBeDisabled()
  })
})
