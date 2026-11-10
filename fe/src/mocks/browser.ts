// Моки в браузере: запускаются из main.tsx только в режиме npm run dev:mock
import { setupWorker } from 'msw/browser'

import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
