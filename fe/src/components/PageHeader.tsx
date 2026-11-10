import { useEffect, type ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  /** Кнопки справа от заголовка */
  actions?: ReactNode
}

/** Заголовок экрана: h1, пояснение и действия. Заодно задаёт заголовок вкладки. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  useEffect(() => {
    document.title = `${title} · reo`
  }, [title])

  return (
    <header className="flex items-end justify-between gap-6">
      <div className="flex min-w-0 flex-col gap-1.5">
        <h1 className="text-h1">{title}</h1>
        {description && <p className="text-small text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}
