import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cx } from '../lib/cx'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  text?: ReactNode
  actions?: ReactNode
  /** error — ошибка: красный значок. Ошибку и пустое состояние различают текст и значок, цвет только дополняет. */
  tone?: 'empty' | 'error'
}

/** Пустое состояние или ошибка в карточке на всю ширину (EmptyBlock в макете) */
export function EmptyState({ icon: Icon, title, text, actions, tone = 'empty' }: EmptyStateProps) {
  return (
    <section className="flex flex-col items-center gap-3 rounded-sheet border border-line bg-surface px-6 py-14 text-center">
      <div
        className={cx(
          'flex size-12 items-center justify-center rounded-full',
          tone === 'error' ? 'bg-neg-tint text-neg-ink' : 'bg-surface-3 text-ink-2',
        )}
      >
        <Icon aria-hidden className="size-5.5" strokeWidth={1.75} />
      </div>
      <h2 className="max-w-115 text-widget">{title}</h2>
      {text && <p className="max-w-115 text-small text-ink-2">{text}</p>}
      {actions && <div className="flex items-center gap-2 pt-1">{actions}</div>}
    </section>
  )
}
