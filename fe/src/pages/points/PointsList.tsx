import { CircleCheck, CircleMinus, CirclePause, Ellipsis, Pencil, RefreshCw, Trash2, TriangleAlert } from 'lucide-react'
import { useId, useRef, useState, type KeyboardEvent } from 'react'

import type { Point } from '../../api/points'

const statuses = {
  no_sources: { label: 'Нет источников', color: 'text-ink-3', icon: CircleMinus },
  collecting: { label: 'Идёт сбор', color: 'text-ink-2', icon: RefreshCw },
  ok: { label: 'Данные актуальны', color: 'text-pos-ink', icon: CircleCheck },
  error: { label: 'Ошибка', color: 'text-neg-ink', icon: TriangleAlert },
  paused: { label: 'Приостановлено', color: 'text-ink-3', icon: CirclePause },
} as const

function PointStatus({ status }: { status: string }) {
  if (!Object.hasOwn(statuses, status)) return <span className="text-ink-3">—</span>
  const { label, color, icon: Icon } = statuses[status as keyof typeof statuses]
  return (
    <span className={`inline-flex items-center gap-1.5 text-small ${color}`}>
      <Icon aria-hidden className="size-3.5 shrink-0" strokeWidth={1.75} />
      {label}
    </span>
  )
}

function PointActions({ point, onEdit, onDelete }: { point: Point; onEdit: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const menuId = useId()
  const actionClass = 'flex w-full cursor-pointer items-center gap-2 rounded-ctl px-3 py-2 text-left text-small hover:bg-hover'

  function choose(action: () => void) {
    trigger.current?.focus()
    setOpen(false)
    action()
  }

  function closeOnEscape(event: KeyboardEvent<HTMLButtonElement>) {
    if (!open || event.key !== 'Escape') return
    event.stopPropagation()
    trigger.current?.focus()
    setOpen(false)
  }

  return (
    <div
      className="relative inline-flex"
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}
    >
      <button
        ref={trigger}
        type="button"
        aria-label={`Действия для точки «${point.name}»`}
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className="inline-flex size-10 cursor-pointer items-center justify-center rounded-ctl text-ink-2 hover:bg-surface-3 aria-expanded:bg-surface-3 sm:size-7.5"
        onClick={() => setOpen((value) => !value)}
        onKeyDown={closeOnEscape}
      >
        <Ellipsis aria-hidden className="size-4.5" strokeWidth={1.75} />
      </button>
      {open && (
        <div id={menuId} className="absolute top-full right-0 z-10 mt-1 w-52 rounded-ctl border border-line bg-surface p-1 shadow-pop">
          <button type="button" className={actionClass} onClick={() => choose(onEdit)} onKeyDown={closeOnEscape}>
            <Pencil aria-hidden className="size-4" strokeWidth={1.75} /> Изменить
          </button>
          <div className="my-1 border-t border-line" />
          <button type="button" className={`${actionClass} text-neg-ink`} onClick={() => choose(onDelete)} onKeyDown={closeOnEscape}>
            <Trash2 aria-hidden className="size-4" strokeWidth={1.75} /> Удалить
          </button>
        </div>
      )}
    </div>
  )
}

interface PointsListProps {
  points: Point[]
  onEdit: (point: Point) => void
  onDelete: (point: Point) => void
}

export function PointsList({ points, onEdit, onDelete }: PointsListProps) {
  return (
    <div className="@container">
      <table aria-label="Точки" className="block w-full text-left @3xl:table @3xl:rounded-sheet @3xl:border @3xl:border-line @3xl:bg-surface @3xl:border-separate @3xl:border-spacing-0">
        <thead className="sr-only @3xl:not-sr-only @3xl:table-header-group">
          <tr className="text-caption text-ink-3">
            <th scope="col" className="px-4 py-3 font-medium">Название и адрес</th>
            <th scope="col" className="w-[18%] px-3 py-3 font-medium">Категория</th>
            <th scope="col" className="w-32.5 px-3 py-3 text-right font-medium">Подключения</th>
            <th scope="col" className="w-[23%] px-4 py-3 font-medium">Статус данных</th>
            <th scope="col" className="w-14"><span className="sr-only">Действия</span></th>
          </tr>
        </thead>
        <tbody className="flex flex-col gap-2 @3xl:table-row-group">
          {points.map((point) => (
            <tr key={point.id} className="relative flex min-h-14 flex-wrap items-center gap-x-3 gap-y-2 rounded-card border border-line bg-surface p-3.5 text-small @3xl:table-row @3xl:border-0 @3xl:hover:bg-row-hover">
              <th scope="row" className="w-full min-w-0 pr-12 text-left font-normal @3xl:w-auto @3xl:border-t @3xl:border-line-soft @3xl:px-4 @3xl:py-2">
                <button type="button" onClick={() => onEdit(point)} className="block cursor-pointer text-left text-body font-semibold wrap-anywhere hover:underline">
                  {point.name}
                </button>
                <span className="block text-caption wrap-anywhere text-ink-3">{point.address}</span>
              </th>
              <td className="max-w-full wrap-anywhere text-ink-2 @3xl:border-t @3xl:border-line-soft @3xl:px-3 @3xl:py-2">
                {point.category || <span className="hidden @3xl:inline">—</span>}
              </td>
              <td className="text-ink-2 tabular-nums @3xl:border-t @3xl:border-line-soft @3xl:px-3 @3xl:py-2 @3xl:text-right">
                <span className="@3xl:hidden">Подключений: </span>{point.sources_count}
              </td>
              <td className="@3xl:border-t @3xl:border-line-soft @3xl:px-4 @3xl:py-2">
                <PointStatus status={point.data_status} />
              </td>
              <td className="absolute top-2 right-2 @3xl:static @3xl:border-t @3xl:border-line-soft @3xl:px-3 @3xl:py-2 @3xl:text-right">
                <PointActions point={point} onEdit={() => onEdit(point)} onDelete={() => onDelete(point)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
