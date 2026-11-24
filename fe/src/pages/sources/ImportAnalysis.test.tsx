import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { API_URL } from '../../api/client'
import type { ImportAnalysis } from '../../api/importAnalysis'
import { csvImportHandlers, demoImportPoint, demoImportResult } from '../../mocks/csvImport'
import { server } from '../../mocks/node'
import { renderApp } from '../../test/render'

const importId = demoImportResult.import_id
const analysisUrl = `${API_URL}/imports/${importId}/analysis`
const pending = { import_id: importId, status: 'pending', result: null, error: null } satisfies ImportAnalysis
const running = { import_id: importId, status: 'running', result: null, error: null } satisfies ImportAnalysis
const done = {
  import_id: importId,
  status: 'done',
  result: { sentiment_counts: { positive: 1, neutral: 1, negative: 1 }, satisfaction_index: 62.5 },
  error: null,
} satisfies ImportAnalysis

async function uploadCsv(user: ReturnType<typeof userEvent.setup>, name = 'reviews.csv') {
  await user.click(await screen.findByRole('button', { name: 'Импорт CSV' }))
  const dialog = within(screen.getByRole('dialog', { name: 'Импорт отзывов из CSV' }))
  await dialog.findByRole('option', { name: /Зерно на Тверской/ })
  await user.selectOptions(dialog.getByRole('combobox'), demoImportPoint.id)
  await user.upload(dialog.getByLabelText('CSV-файл'), new File([
    'date,text,rating\n2026-11-20,Хороший кофе,5',
  ], name, { type: 'text/csv' }))
  await user.click(dialog.getByRole('button', { name: 'Импортировать' }))
}

async function openImportReport(result = demoImportResult) {
  server.use(http.post(`${API_URL}/imports/csv`, () => HttpResponse.json(result, { status: 201 })))
  const user = userEvent.setup()
  renderApp('/sources')
  await uploadCsv(user)
  return user
}

describe('Анализ CSV-импорта', () => {
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

  it('запускает анализ выбранного импорта без тела запроса и опрашивает статус до результата', async () => {
    const start = vi.fn<({ request }: { request: Request }) => Response>(({ request }) => {
      expect(request.headers.has('Content-Type')).toBe(false)
      return HttpResponse.json(running, { status: 202 })
    })
    const status = vi.fn<() => Response>()
      .mockImplementationOnce(() => HttpResponse.json(running))
      .mockImplementation(() => HttpResponse.json(done))
    server.use(http.post(analysisUrl, start), http.get(analysisUrl, status))
    const user = await openImportReport()
    const button = await screen.findByRole('button', { name: 'Запустить анализ' })
    expect(start).not.toHaveBeenCalled()
    expect(status).not.toHaveBeenCalled()
    await user.click(button)

    expect(await screen.findByText('Анализ выполняется…')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Запустить анализ' })).not.toBeInTheDocument()
    expect(await screen.findByText('62,5', {}, { timeout: 6_000 })).toBeInTheDocument()
    expect(screen.getByText('Позитивные').nextElementSibling).toHaveTextContent('1')
    expect(screen.getByText('Нейтральные').nextElementSibling).toHaveTextContent('1')
    expect(screen.getByText('Негативные').nextElementSibling).toHaveTextContent('1')
    expect(start).toHaveBeenCalledTimes(1)
    expect(status).toHaveBeenCalledTimes(2)
  }, 9_000)

  it.each([
    { index: 0, text: '0', counts: { positive: 0, neutral: 0, negative: 3 } },
    { index: null, text: 'Недостаточно данных', counts: { positive: 0, neutral: 0, negative: 0 } },
  ])('показывает мгновенный результат с индексом $index без опроса', async ({ index, text, counts }) => {
    const status = vi.fn<() => Response>(() => HttpResponse.json(done))
    server.use(
      http.post(analysisUrl, () => HttpResponse.json({
        ...done, result: { sentiment_counts: counts, satisfaction_index: index },
      })),
      http.get(analysisUrl, status),
    )
    const user = await openImportReport()
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))
    const analysis = within(screen.getByRole('region', { name: 'Анализ отзывов' }))
    expect(await analysis.findByText('Анализ завершён')).toBeInTheDocument()
    expect(analysis.getByText('Индекс удовлетворённости').nextElementSibling).toHaveTextContent(text)
    expect(status).not.toHaveBeenCalled()
  })

  it('показывает частичный результат после сбоя ML и позволяет повторить анализ', async () => {
    const partial = {
      import_id: importId,
      status: 'error',
      result: { sentiment_counts: { positive: 1, neutral: 0, negative: 0 }, satisfaction_index: 85 },
      error: { code: 'ml_error', message: 'Не удалось обработать часть или все отзывы' },
    } satisfies ImportAnalysis
    const start = vi.fn<() => Response>()
      .mockImplementationOnce(() => HttpResponse.json(running, { status: 202 }))
      .mockImplementation(() => HttpResponse.json(done))
    server.use(http.post(analysisUrl, start), http.get(analysisUrl, () => HttpResponse.json(partial)))
    const user = await openImportReport()
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))

    expect(await screen.findByRole('alert', {}, { timeout: 4_000 })).toHaveTextContent('результат по обработанным отзывам')
    expect(screen.getByText('85')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Повторить анализ' }))
    expect(await screen.findByText('62,5')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(start).toHaveBeenCalledTimes(2)
  })

  it('после ошибки опроса проверяет статус без повторного запуска анализа', async () => {
    const start = vi.fn<() => Response>(() => HttpResponse.json(running, { status: 202 }))
    const status = vi.fn<() => Response>()
      .mockImplementationOnce(() => HttpResponse.error())
      .mockImplementation(() => HttpResponse.json(done))
    server.use(http.post(analysisUrl, start), http.get(analysisUrl, status))
    const user = await openImportReport()
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))

    expect(await screen.findByRole('alert', {}, { timeout: 4_000 })).toHaveTextContent('Не удалось проверить статус анализа')
    await user.click(screen.getByRole('button', { name: 'Проверить статус' }))
    expect(await screen.findByText('62,5')).toBeInTheDocument()
    expect(start).toHaveBeenCalledTimes(1)
    expect(status).toHaveBeenCalledTimes(2)
  })

  it('сохраняет действие запуска, когда сервер занят', async () => {
    server.use(http.post(analysisUrl, () => HttpResponse.json({
      error: { code: 'analysis_busy', message: 'Все обработчики анализа заняты. Повторите запрос позже', details: null },
    }, { status: 503 })))
    const user = await openImportReport()
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Все обработчики анализа заняты')
    expect(screen.getByRole('button', { name: 'Запустить анализ' })).toBeEnabled()
  })

  it('запрашивает анализ импорта одних дублей и показывает нулевое распределение', async () => {
    const start = vi.fn<() => Response>(() => HttpResponse.json({
      ...done,
      result: { sentiment_counts: { positive: 0, neutral: 0, negative: 0 }, satisfaction_index: null },
    }))
    server.use(http.post(analysisUrl, start))
    const user = await openImportReport({ ...demoImportResult, imported: 0, duplicates: 3 })
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))

    expect(await screen.findByText('Недостаточно данных')).toBeInTheDocument()
    for (const label of ['Позитивные', 'Нейтральные', 'Негативные']) {
      expect(screen.getByText(label).nextElementSibling).toHaveTextContent('0')
    }
    expect(start).toHaveBeenCalledTimes(1)
  })

  it('сохраняет отчёт при переходе и восстанавливает состояние анализа после обновления', async () => {
    const start = vi.fn<() => Response>(() => HttpResponse.json(done))
    const status = vi.fn<() => Response>(() => HttpResponse.json(done))
    server.use(
      http.post(`${API_URL}/imports/csv`, () => HttpResponse.json(demoImportResult, { status: 201 })),
      http.post(analysisUrl, start),
      http.get(analysisUrl, status),
    )
    const user = userEvent.setup()
    const page = renderApp('/sources')
    await uploadCsv(user)
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText('62,5')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Точки' }))
    expect(await screen.findByRole('heading', { name: 'Точки' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Источники' }))
    expect(await screen.findByText('62,5')).toBeInTheDocument()

    page.unmount()
    renderApp('/sources')
    expect(await screen.findByText(/reviews\.csv/)).toBeInTheDocument()
    expect(await screen.findByText('62,5')).toBeInTheDocument()
    expect(status).toHaveBeenCalledTimes(1)
    expect(start).toHaveBeenCalledTimes(1)
  })

  it('продолжает опрос, если GET при возврате запоздал с ответом pending', async () => {
    let releaseStart!: () => void
    let releaseStatus!: () => void
    const startResponse = new Promise<void>((resolve) => { releaseStart = resolve })
    const statusResponse = new Promise<void>((resolve) => { releaseStatus = resolve })
    const start = vi.fn<() => Promise<Response>>(async () => {
      await startResponse
      return HttpResponse.json(running, { status: 202 })
    })
    const status = vi.fn<() => Promise<Response>>()
      .mockImplementationOnce(async () => {
        await statusResponse
        return HttpResponse.json(pending)
      })
      .mockImplementation(async () => HttpResponse.json(done))
    server.use(http.post(analysisUrl, start), http.get(analysisUrl, status))
    const user = await openImportReport()
    try {
      await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))
      await waitFor(() => expect(start).toHaveBeenCalledTimes(1))
      await user.click(screen.getByRole('link', { name: 'Точки' }))
      await screen.findByRole('heading', { name: 'Точки' })
      await user.click(screen.getByRole('link', { name: 'Источники' }))
      await waitFor(() => expect(status).toHaveBeenCalledTimes(1))

      releaseStart()
      expect(await screen.findByText('Анализ выполняется…')).toBeInTheDocument()
      releaseStatus()
      expect(await screen.findByText('62,5', {}, { timeout: 4_000 })).toBeInTheDocument()
      expect(status).toHaveBeenCalledTimes(2)
    } finally {
      releaseStart()
      releaseStatus()
    }
  }, 8_000)

  it('удаляет отчёт из кеша и хранилища при удалении его точки', async () => {
    let deleted = false
    server.use(
      http.get(`${API_URL}/points`, () => {
        const items = deleted ? [] : [demoImportPoint]
        return HttpResponse.json({ items, total: items.length, limit: 50, offset: 0 })
      }),
      http.delete(`${API_URL}/points/${demoImportPoint.id}`, () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
      http.post(`${API_URL}/imports/csv`, () => HttpResponse.json(demoImportResult, { status: 201 })),
      http.post(analysisUrl, () => HttpResponse.json(done)),
    )
    const user = userEvent.setup()
    const page = renderApp('/sources')
    await uploadCsv(user)
    await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))
    expect(await screen.findByText('62,5')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Точки' }))
    await user.click(await screen.findByRole('button', { name: 'Действия для точки «Зерно на Тверской»' }))
    await user.click(screen.getByRole('button', { name: 'Удалить' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Удалить точку' }))
    await screen.findByRole('heading', { name: 'Точек пока нет' })

    await user.click(screen.getByRole('link', { name: 'Источники' }))
    expect(await screen.findByRole('heading', { name: 'Импорт отзывов' })).toBeInTheDocument()
    page.unmount()
    renderApp('/sources')
    expect(await screen.findByRole('heading', { name: 'Импорт отзывов' })).toBeInTheDocument()
  })

  it('удаляет сохранённый отчёт, если API больше не находит импорт', async () => {
    const status = vi.fn<() => Response>(() => HttpResponse.json({
      error: { code: 'not_found', message: 'Импорт не найден', details: null },
    }, { status: 404 }))
    server.use(
      http.post(`${API_URL}/imports/csv`, () => HttpResponse.json(demoImportResult, { status: 201 })),
      http.get(analysisUrl, status),
    )
    const user = userEvent.setup()
    const page = renderApp('/sources')
    await uploadCsv(user)
    expect(await screen.findByText(/reviews\.csv/)).toBeInTheDocument()
    page.unmount()

    const reloaded = renderApp('/sources')
    expect(await screen.findByRole('heading', { name: 'Импорт отзывов' })).toBeInTheDocument()
    reloaded.unmount()
    renderApp('/sources')
    expect(await screen.findByRole('heading', { name: 'Импорт отзывов' })).toBeInTheDocument()
    expect(status).toHaveBeenCalledTimes(1)
  })

  it('восстанавливает запущенный мок-анализ при повторном создании обработчиков', async () => {
    const hasPoint = (id: string) => id === demoImportPoint.id
    server.use(...csvImportHandlers(hasPoint, sessionStorage))
    const form = new FormData()
    form.set('point_id', demoImportPoint.id)
    form.set('file', new File(['date,text\n2026-11-20,Хороший кофе'], 'reviews.csv', { type: 'text/csv' }))
    // Подменяем разбор multipart из-за разных реализаций File в Node и jsdom.
    const decode = vi.spyOn(Request.prototype, 'formData').mockResolvedValueOnce(form)
    const now = vi.spyOn(Date, 'now').mockReturnValue(10_000)
    try {
      const upload = await fetch(`${API_URL}/imports/csv`, { method: 'POST' })
      expect(upload.status).toBe(201)
      const { import_id: id } = await upload.json() as { import_id: string }
      const url = `${API_URL}/imports/${id}/analysis`
      expect((await fetch(url, { method: 'POST' })).status).toBe(202)

      server.use(...csvImportHandlers(hasPoint, sessionStorage))
      const restored = await fetch(url)
      expect(restored.status).toBe(200)
      expect(await restored.json()).toMatchObject({ import_id: id, status: 'running' })
      now.mockReturnValue(13_000)
      expect(await (await fetch(url)).json()).toMatchObject({ import_id: id, status: 'done' })
    } finally {
      decode.mockRestore()
      now.mockRestore()
    }
  })

  it('не переносит результат запущенного анализа в отчёт нового импорта', async () => {
    const nextId = '41849a47-5166-4ec0-a94a-54b3b47289e2'
    let releaseResponse!: () => void
    const response = new Promise<void>((resolve) => { releaseResponse = resolve })
    const oldStatus = vi.fn<() => Promise<Response>>(async () => {
      await response
      return HttpResponse.json(done)
    })
    const nextStart = vi.fn<() => Response>(() => HttpResponse.json({
      ...done, import_id: nextId, result: { ...done.result, satisfaction_index: 77 },
    }))
    server.use(
      http.post(analysisUrl, () => HttpResponse.json(running, { status: 202 })),
      http.get(analysisUrl, oldStatus),
      http.post(`${API_URL}/imports/${nextId}/analysis`, nextStart),
    )
    const user = await openImportReport()
    try {
      await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))
      await waitFor(() => expect(oldStatus).toHaveBeenCalled(), { timeout: 4_000 })
      server.use(http.post(`${API_URL}/imports/csv`, () =>
        HttpResponse.json({ ...demoImportResult, import_id: nextId }, { status: 201 }),
      ))
      await uploadCsv(user, 'next.csv')
      expect(await screen.findByText(/next\.csv/)).toBeInTheDocument()
      releaseResponse()
      await user.click(await screen.findByRole('button', { name: 'Запустить анализ' }))
      expect(await screen.findByText('77')).toBeInTheDocument()
      expect(screen.queryByText('62,5')).not.toBeInTheDocument()
      expect(nextStart).toHaveBeenCalledTimes(1)
    } finally {
      releaseResponse()
    }
  })
})
