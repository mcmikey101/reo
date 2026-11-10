import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from '../mocks/node'

// jsdom не умеет прокручивать окно, а ScrollRestoration вызывает scrollTo
window.scrollTo = () => {}

// Любой запрос без мока — ошибка теста: так не пропустим лишний вызов API
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))

afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear()
})

afterAll(() => server.close())
