import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderApp } from './test/render'

describe('каркас приложения', () => {
  it('с корня открывает дашборд', async () => {
    const { router } = renderApp('/')

    expect(await screen.findByRole('heading', { level: 1, name: 'Дашборд' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/dashboard')
    expect(screen.getByRole('link', { name: 'Дашборд' })).toHaveAttribute('aria-current', 'page')
  })

  it.each([
    ['/dashboard', 'Дашборд', 'Данных для анализа пока нет'],
    ['/summary', 'Суммаризация', 'Суммаризация ещё не сформирована'],
    ['/points', 'Точки', 'Точек пока нет'],
    ['/sources', 'Источники', 'Источников пока нет'],
    ['/settings', 'Настройки', 'Настройки пока недоступны'],
  ])('%s — экран «%s» с пустым состоянием', async (path, title, emptyTitle) => {
    renderApp(path)

    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: emptyTitle })).toBeInTheDocument()
  })

  it('в интерфейсе название reo, а не «Отклик»', async () => {
    renderApp('/')

    expect(await screen.findByRole('link', { name: 'reo' })).toBeInTheDocument()
    expect(screen.queryByText(/Отклик/)).not.toBeInTheDocument()
  })

  it('пункты меню переключают экраны', async () => {
    const user = userEvent.setup()
    renderApp('/dashboard')
    const nav = await screen.findByRole('navigation', { name: 'Основное меню' })

    await user.click(within(nav).getByRole('link', { name: 'Точки' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Точки' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Точки' })).toHaveAttribute('aria-current', 'page')
    expect(document.title).toBe('Точки · reo')
  })

  it('меню сворачивается, пункты остаются доступными, выбор запоминается', async () => {
    const user = userEvent.setup()
    const first = renderApp('/dashboard')

    await user.click(await screen.findByRole('button', { name: 'Свернуть меню' }))

    expect(screen.getByRole('button', { name: 'Развернуть меню' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('link', { name: 'Источники' })).toHaveAttribute('title', 'Источники')
    expect(localStorage.getItem('reo.sidebar.collapsed')).toBe('1')

    first.unmount()
    renderApp('/dashboard')
    expect(await screen.findByRole('button', { name: 'Развернуть меню' })).toBeInTheDocument()
  })

  it('неизвестный адрес — страница «не найдена» внутри каркаса', async () => {
    renderApp('/no-such-page')

    expect(await screen.findByRole('heading', { level: 1, name: 'Страница не найдена' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Основное меню' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'На дашборд' })).toHaveAttribute('href', '/dashboard')
  })
})
