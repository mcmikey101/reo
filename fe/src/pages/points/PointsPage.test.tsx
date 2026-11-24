import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { API_URL } from '../../api/client'
import { server } from '../../mocks/node'
import { pointHandlers } from '../../mocks/points'
import { renderApp } from '../../test/render'

const pointsUrl = `${API_URL}/points`

async function openNewPoint(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('heading', { name: 'Точек пока нет' })
  await user.click(screen.getByRole('button', { name: 'Добавить точку' }))
  return screen.getByRole('dialog', { name: 'Новая точка' })
}

async function enterPoint(user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, name: string, address: string) {
  await user.type(within(dialog).getByRole('textbox', { name: 'Название' }), name)
  await user.type(within(dialog).getByRole('textbox', { name: 'Адрес' }), address)
}

describe('REO-33 · точки', () => {
  beforeAll(() => {
    // jsdom не реализует императивное открытие нативного <dialog>.
    HTMLDialogElement.prototype.showModal ??= function () { this.open = true }
    HTMLDialogElement.prototype.close ??= function () { this.open = false }
  })
  beforeEach(() => { server.use(...pointHandlers()) })

  it('создаёт, редактирует и удаляет точку, загружая сохранённые данные заново', async () => {
    const user = userEvent.setup()
    const first = renderApp('/points')
    const dialog = await openNewPoint(user)
    await enterPoint(user, dialog, 'Арбат', 'Арбат, 24')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByRole('button', { name: 'Арбат' })).toBeInTheDocument()
    first.unmount()

    const second = renderApp('/points')
    await user.click(await screen.findByRole('button', { name: 'Арбат' }))
    const form = screen.getByRole('dialog', { name: 'Изменить точку' })
    const address = within(form).getByRole('textbox', { name: 'Адрес' })
    expect(address).toHaveValue('Арбат, 24')
    await user.clear(address)
    await user.type(address, 'Арбат, 26')
    await user.click(within(form).getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Арбат, 26')).toBeInTheDocument()
    second.unmount()

    const third = renderApp('/points')
    expect(await screen.findByText('Арбат, 26')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Действия для точки «Арбат»' }))
    await user.click(screen.getByRole('button', { name: 'Удалить' }))
    const remove = screen.getByRole('dialog', { name: 'Удалить точку «Арбат»?' })
    expect(within(remove).getByText(/источники и отзывы/)).toBeInTheDocument()
    await user.click(within(remove).getByRole('button', { name: 'Отмена' }))
    expect(screen.getByText('Арбат, 26')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Действия для точки «Арбат»' }))
    await user.click(screen.getByRole('button', { name: 'Удалить' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Удалить точку' }))
    expect(await screen.findByRole('heading', { name: 'Точек пока нет' })).toBeInTheDocument()
    third.unmount()
    renderApp('/points')
    expect(await screen.findByRole('heading', { name: 'Точек пока нет' })).toBeInTheDocument()
  })

  it('отображает ошибки формы и записывает дубль только после явного подтверждения', async () => {
    const user = userEvent.setup()
    renderApp('/points')
    const first = await openNewPoint(user)
    await user.click(within(first).getByRole('button', { name: 'Сохранить' }))
    expect(within(first).getByText('Укажите название')).toBeInTheDocument()

    await enterPoint(user, first, 'Север', 'Москва, 1')
    server.use(http.post(pointsUrl, () => HttpResponse.json({ error: {
      code: 'validation_error', message: 'Проверьте поля формы',
      details: { fields: [{ field: 'address', code: 'invalid_value', message: 'Проверьте адрес' }] },
    } }, { status: 422 }), { once: true }))
    await user.click(within(first).getByRole('button', { name: 'Сохранить' }))
    expect(await within(first).findByText('Проверьте адрес')).toBeInTheDocument()
    expect(within(first).getByRole('textbox', { name: 'Адрес' })).toHaveValue('Москва, 1')
    await user.click(within(first).getByRole('button', { name: 'Сохранить' }))
    await screen.findByRole('button', { name: 'Север' })

    await user.click(screen.getByRole('button', { name: 'Добавить точку' }))
    const second = screen.getByRole('dialog', { name: 'Новая точка' })
    await enterPoint(user, second, 'север', 'Москва,  1')
    await user.click(within(second).getByRole('button', { name: 'Сохранить' }))
    expect(await within(second).findByText('Возможный дубль')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(2)
    await user.click(within(second).getByRole('button', { name: 'Сохранить всё равно' }))
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(3))
  })
})
