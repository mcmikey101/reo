import { CircleAlert, RotateCw } from 'lucide-react'
import { useRouteError } from 'react-router'

import { buttonClass } from '../components/button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'

/** Ошибка при отрисовке экрана. Шапка и меню остаются, чтобы можно было уйти на другой экран. */
export function RouteErrorPage() {
  const error = useRouteError()

  return (
    <>
      <PageHeader title="Ошибка" />
      <EmptyState
        tone="error"
        icon={CircleAlert}
        title="Не удалось показать страницу"
        text={
          <>
            Обновите страницу или перейдите на другой экран через меню.
            {import.meta.env.DEV && error instanceof Error && (
              <code className="mt-3 block rounded-ctl bg-surface-2 px-3 py-2 text-left text-caption break-words text-neg-ink">
                {error.message}
              </code>
            )}
          </>
        }
        actions={
          <button type="button" className={buttonClass()} onClick={() => window.location.reload()}>
            <RotateCw aria-hidden className="size-4" strokeWidth={1.75} />
            Обновить
          </button>
        }
      />
    </>
  )
}
