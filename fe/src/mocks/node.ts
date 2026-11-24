// Моки в тестах (Vitest): подключаются в src/test/setup.ts
import { setupServer } from 'msw/node'

import { handlers } from './handlers'
import { pointHandlers } from './points'

export const server = setupServer(...handlers, ...pointHandlers())
