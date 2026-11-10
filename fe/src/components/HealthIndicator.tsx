import { CircleCheck, CircleDashed, CircleX, type LucideIcon } from 'lucide-react'
import { Fragment, useEffect, useId, useState } from 'react'

import { API_URL, ApiError } from '../api/client'
import { useHealth, type PartStatus } from '../api/health'
import { cx } from '../lib/cx'
import { formatTime } from '../lib/format'

type Light = 'pending' | 'ok' | 'error'
type PartKey = 'api' | 'db' | 'ml'

interface PartView {
  light: Light
  /** Состояние словами: для подсказки и экранного диктора */
  text: string
}

const PARTS: { key: PartKey; label: string; name: string }[] = [
  { key: 'api', label: 'API', name: 'API' },
  { key: 'db', label: 'БД', name: 'База данных' },
  { key: 'ml', label: 'ML', name: 'ML-сервис' },
]

// Состояние различается не только цветом, но и значком (docs/screens.md, «Состояния»)
const ICONS: Record<Light, LucideIcon> = { pending: CircleDashed, ok: CircleCheck, error: CircleX }
const COLORS: Record<Light, string> = { pending: 'text-ink-3', ok: 'text-pos-ink', error: 'text-neg-ink' }

function apiProblem(error: Error): string {
  if (!(error instanceof ApiError)) return 'ошибка'
  switch (error.kind) {
    case 'network':
      return 'не отвечает'
    case 'timeout':
      return 'не ответил вовремя'
    case 'http':
      return `ошибка ${error.status}`
    case 'parse':
      return 'неожиданный ответ'
  }
}

function fromStatus(status: PartStatus, okText: string, errorText: string): PartView {
  return status === 'ok' ? { light: 'ok', text: okText } : { light: 'error', text: errorText }
}

function describe(health: ReturnType<typeof useHealth>): Record<PartKey, PartView> {
  if (health.status === 'pending') {
    const pending: PartView = { light: 'pending', text: 'проверяется' }
    return { api: pending, db: pending, ml: pending }
  }
  if (health.status === 'error') {
    // Без ответа API состояние БД и ML неизвестно — для пользователя они тоже не работают
    const unknown: PartView = { light: 'error', text: 'не проверено' }
    return { api: { light: 'error', text: apiProblem(health.error) }, db: unknown, ml: unknown }
  }
  return {
    api: { light: 'ok', text: 'отвечает' },
    db: fromStatus(health.data.db, 'доступна', 'недоступна'),
    ml: fromStatus(health.data.ml, 'доступен', 'недоступен'),
  }
}

/**
 * Индикатор «API · БД · ML» в шапке. Опрашивает GET {VITE_API_URL}/health.
 * Если API недоступен, все три части красные, а страница продолжает работать.
 * Нажатие — проверить сейчас, наведение или фокус — подробности.
 */
export function HealthIndicator() {
  const health = useHealth()
  const parts = describe(health)
  const tooltipId = useId()
  const [tipOpen, setTipOpen] = useState(false)

  // Подсказку можно закрыть клавишей Esc, не уводя мышь и фокус
  useEffect(() => {
    if (!tipOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setTipOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [tipOpen])

  const summary = PARTS.map(({ key, label }) => `${label} ${parts[key].text}`).join(', ')
  const checkedAt = Math.max(health.dataUpdatedAt, health.errorUpdatedAt)

  return (
    <div className="relative" onMouseEnter={() => setTipOpen(true)} onMouseLeave={() => setTipOpen(false)}>
      <button
        type="button"
        aria-label={`Состояние системы: ${summary}. Проверить снова`}
        aria-describedby={tooltipId}
        aria-busy={health.isFetching}
        onClick={() => void health.refetch()}
        onFocus={() => setTipOpen(true)}
        onBlur={() => setTipOpen(false)}
        className="flex h-8.5 cursor-pointer items-center gap-1.5 rounded-ctl border border-line bg-surface px-3 text-small font-medium transition-colors hover:bg-hover"
      >
        {PARTS.map(({ key, label }, index) => {
          const { light } = parts[key]
          const Icon = ICONS[light]
          return (
            <Fragment key={key}>
              {index > 0 && (
                <span aria-hidden className="text-ink-3">
                  ·
                </span>
              )}
              <span data-part={key} data-status={light} className={cx('inline-flex items-center gap-1', COLORS[light])}>
                <Icon aria-hidden className="size-3.5" strokeWidth={2.25} />
                {label}
              </span>
            </Fragment>
          )
        })}
      </button>

      <div id={tooltipId} role="tooltip" hidden={!tipOpen} className="absolute top-full right-0 z-30 pt-2">
        <div className="w-72 rounded-ctl bg-tip px-3 py-2.5 text-caption text-white shadow-pop">
          <p className="font-semibold">Состояние системы</p>
          <dl className="mt-1.5 flex flex-col gap-1">
            {PARTS.map(({ key, name }) => (
              <div key={key} className="flex justify-between gap-3">
                <dt className="text-tip-ink-2">{name}</dt>
                <dd className="font-semibold">{parts[key].text}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-2 flex flex-col gap-0.5 border-t border-white/15 pt-2 text-tip-ink-2">
            <p>{checkedAt > 0 ? `Проверено в ${formatTime(checkedAt)}` : 'Проверяем…'}</p>
            <p className="break-all">Адрес API: {API_URL}</p>
            <p>Нажмите, чтобы проверить снова</p>
          </div>
        </div>
      </div>
    </div>
  )
}
