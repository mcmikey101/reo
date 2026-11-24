// Моки в браузере: запускаются из main.tsx только в режиме npm run dev:mock
import { setupWorker } from 'msw/browser'

import { handlers } from './handlers'
import { pointHandlers } from './points'

export const worker = setupWorker(...handlers, ...pointHandlers(window.localStorage, window.sessionStorage))
