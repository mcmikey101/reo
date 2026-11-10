import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { API_URL } from '../api/client'
import { server } from '../mocks/node'
import { renderWithQuery } from '../test/render'
import { HealthIndicator } from './HealthIndicator'

const healthUrl = `${API_URL}/health`

function statusOf(part: 'api' | 'db' | 'ml') {
  return document.querySelector(`[data-part="${part}"]`)?.getAttribute('data-status')
}

async function waitForChecked() {
  await waitFor(() => expect(statusOf('api')).not.toBe('pending'))
}

describe('HealthIndicator', () => {
  it('всё работает — три части зелёные', async () => {
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()

    expect([statusOf('api'), statusOf('db'), statusOf('ml')]).toEqual(['ok', 'ok', 'ok'])
    expect(screen.getByRole('button', { name: /API отвечает, БД доступна, ML доступен/ })).toBeInTheDocument()
  })

  it('БД недоступна — красная только БД', async () => {
    server.use(http.get(healthUrl, () => HttpResponse.json({ status: 'ok', db: 'error', ml: 'ok' })))
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()

    expect([statusOf('api'), statusOf('db'), statusOf('ml')]).toEqual(['ok', 'error', 'ok'])
  })

  it('API недоступен — всё красное, компонент не падает', async () => {
    server.use(http.get(healthUrl, () => HttpResponse.error()))
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()

    expect([statusOf('api'), statusOf('db'), statusOf('ml')]).toEqual(['error', 'error', 'error'])
    expect(screen.getByRole('button', { name: /API не отвечает/ })).toBeInTheDocument()
  })

  it('ответ 500 — красный', async () => {
    server.use(
      http.get(healthUrl, () =>
        HttpResponse.json(
          { error: { code: 'internal_error', message: 'Ошибка сервера', details: null } },
          { status: 500 },
        ),
      ),
    )
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()

    expect(statusOf('api')).toBe('error')
    expect(screen.getByRole('button', { name: /API ошибка 500/ })).toBeInTheDocument()
  })

  it('ответ не по формату — красный', async () => {
    server.use(http.get(healthUrl, () => HttpResponse.json({ status: 'ok' })))
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()

    expect(statusOf('api')).toBe('error')
    expect(screen.getByRole('button', { name: /API неожиданный ответ/ })).toBeInTheDocument()
  })

  it('нажатие проверяет снова и обновляет цвет', async () => {
    server.use(http.get(healthUrl, () => HttpResponse.error()))
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()
    expect(statusOf('api')).toBe('error')

    server.resetHandlers()
    await userEvent.click(screen.getByRole('button', { name: /Состояние системы/ }))

    await waitFor(() => expect(statusOf('api')).toBe('ok'))
  })

  it('подсказка открывается при фокусе и закрывается по Esc', async () => {
    const user = userEvent.setup()
    renderWithQuery(<HealthIndicator />)
    await waitForChecked()

    await user.tab()
    expect(screen.getByRole('tooltip')).toBeVisible()
    expect(screen.getByRole('tooltip')).toHaveTextContent('База данных')

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
