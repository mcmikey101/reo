import { useQueryClient } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, LoaderCircle, MapPin, Plus, Search, X } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link } from 'react-router'

import { useDeletePoint, usePoints, type Point } from '../../api/points'
import { buttonClass } from '../../components/button'
import { EmptyState } from '../../components/EmptyState'
import { PageHeader } from '../../components/PageHeader'
import { paths } from '../../paths'
import { clearLastImportReport } from '../../state/lastImportReport'
import { PointDialog } from './PointDialog'
import { PointForm } from './PointForm'
import { PointsList } from './PointsList'

type PointAction = { kind: 'add' } | { kind: 'edit' | 'delete'; point: Point }

function DeletePointDialog({ point, onDismiss, onDeleted }: { point: Point; onDismiss: () => void; onDeleted: () => void }) {
  const client = useQueryClient()
  const mutation = useDeletePoint((id) => clearLastImportReport(client, 'point_id', id))

  return (
    <PointDialog
      title={`Удалить точку «${point.name}»?`}
      description="Вместе с точкой будут удалены её источники и отзывы. Восстановить их будет невозможно."
      busy={mutation.isPending}
      onDismiss={onDismiss}
    >
      {mutation.error && <p role="alert" className="mx-5 mt-4 rounded-ctl bg-neg-tint p-3 text-small text-neg-ink sm:mx-6">{mutation.error.message}</p>}
      <div className="flex flex-wrap justify-end gap-2 px-5 py-5 sm:px-6">
        <button type="button" className={buttonClass()} onClick={onDismiss} disabled={mutation.isPending} data-initial-focus>Отмена</button>
        <button
          type="button"
          className={buttonClass({ kind: 'danger' })}
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(point.id, { onSuccess: onDeleted })}
        >
          {mutation.isPending ? 'Удаляем…' : 'Удалить точку'}
        </button>
      </div>
    </PointDialog>
  )
}

/** M1. Точки — docs/screens.md, API — docs/api-contract.md. */
export function PointsPage() {
  const [search, setSearch] = useState('')
  const [action, setAction] = useState<PointAction | null>(null)
  const [notice, setNotice] = useState<{ message: string; pointId?: string } | null>(null)
  const query = useDeferredValue(search.trim())
  const points = usePoints(query)
  const items = points.data?.pages.flatMap((page) => page.items) ?? []
  const total = points.data?.pages[0]?.total
  const empty = total === 0 && !query

  const addButton = (
    <button type="button" className={buttonClass({ kind: 'primary' })} onClick={() => setAction({ kind: 'add' })}>
      <Plus aria-hidden className="size-4" strokeWidth={1.75} /> Добавить точку
    </button>
  )

  return (
    <>
      <PageHeader
        title="Точки"
        description={empty ? undefined : 'Объекты, по которым собираются отзывы'}
        count={empty ? undefined : total}
        actions={empty ? undefined : addButton}
      />
      {(!empty || search) && (
        <div className="relative w-full max-w-90">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" strokeWidth={1.75} />
          <input
            type="search"
            aria-label="Поиск по названию и адресу"
            placeholder="Поиск по названию и адресу"
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="h-11 w-full rounded-ctl border border-input-line bg-surface pr-3 pl-9 text-body placeholder:text-ink-3 sm:h-9"
          />
        </div>
      )}
      {points.isPending ? (
        <output className="flex items-center gap-2 rounded-sheet border border-line bg-surface p-5 text-small text-ink-2">
          <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" /> Загружаем точки…
        </output>
      ) : points.isError && !points.data ? (
        <EmptyState
          icon={CircleAlert}
          title="Не удалось загрузить точки"
          text={points.error.message}
          tone="error"
          actions={<button type="button" className={buttonClass()} onClick={() => void points.refetch()}>Повторить</button>}
        />
      ) : items.length ? (
        <>
          <PointsList points={items} onEdit={(point) => setAction({ kind: 'edit', point })} onDelete={(point) => setAction({ kind: 'delete', point })} />
          {points.isError && (
            <div role="alert" className="flex flex-wrap items-center gap-3 text-small text-neg-ink">
              <p>{points.error.message}</p>
              {!points.isFetchNextPageError && (
                <button type="button" className={buttonClass({ size: 's' })} onClick={() => void points.refetch()}>Повторить</button>
              )}
            </div>
          )}
          {points.hasNextPage && (
            <div>
              <button type="button" className={buttonClass()} disabled={points.isFetching} onClick={() => void points.fetchNextPage()}>
                {points.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё'}
              </button>
            </div>
          )}
        </>
      ) : query ? (
        <EmptyState
          icon={Search}
          title="Точки не найдены"
          text="Попробуйте указать другое название или адрес."
          actions={<button type="button" className={buttonClass()} onClick={() => setSearch('')}>Очистить поиск</button>}
        />
      ) : (
        <EmptyState
          icon={MapPin}
          title="Точек пока нет"
          text="Точка — кофейня, ресторан или другой объект, по которому собираются отзывы."
          actions={addButton}
        />
      )}
      {action?.kind === 'delete' ? (
        <DeletePointDialog
          point={action.point}
          onDismiss={() => setAction(null)}
          onDeleted={() => {
            setAction(null)
            setNotice({ message: `Точка «${action.point.name}» удалена` })
          }}
        />
      ) : action && (
        <PointForm
          point={action.kind === 'edit' ? action.point : undefined}
          onDismiss={() => setAction(null)}
          onSaved={(point, created) => {
            setAction(null)
            setNotice({ message: `Точка «${point.name}» ${created ? 'добавлена' : 'изменена'}`, pointId: created ? point.id : undefined })
            if (created) setSearch('')
          }}
        />
      )}
      {notice && (
        <div className="fixed right-4 bottom-4 z-30 flex max-w-[calc(100%_-_2rem)] flex-wrap items-center gap-2 rounded-card bg-tip px-3 py-2 text-small text-white shadow-pop sm:right-6 sm:bottom-6">
          <CircleCheck aria-hidden className="size-4 shrink-0 text-pos-tint" strokeWidth={1.75} />
          <output className="min-w-0 flex-1 wrap-anywhere">{notice.message}</output>
          {notice.pointId && (
            <Link className="rounded-ctl px-2 py-1 font-medium hover:underline focus-visible:outline-white" to={`${paths.sources}?${new URLSearchParams({ point_id: notice.pointId })}`}>
              Подключить источник
            </Link>
          )}
          <button type="button" aria-label="Закрыть уведомление" className="cursor-pointer rounded-ctl p-1 text-tip-ink-2 hover:text-white focus-visible:outline-white" onClick={() => setNotice(null)}>
            <X aria-hidden className="size-4" strokeWidth={1.75} />
          </button>
        </div>
      )}
    </>
  )
}
