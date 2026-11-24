import { useEffect, type ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  count?: number
  /** Кнопки справа от заголовка */
  actions?: ReactNode
}

/** Заголовок экрана: h1, пояснение и действия. Заодно задаёт заголовок вкладки. */
export function PageHeader({ title, description, count, actions }: PageHeaderProps) {
  useEffect(() => {
    document.title = `${title} · reo`
  }, [title])

  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="flex min-w-0 flex-col gap-1.5">
        <div className="flex items-center gap-2.5">
          <h1 className="text-h1">{title}</h1>
          {count !== undefined && (
            <span aria-label={`Количество: ${count}`} className="rounded-full bg-surface-3 px-2 py-0.5 text-caption text-ink-2 tabular-nums">
              {count}
            </span>
          )}
        </div>
        {description && <p className="text-small text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}
