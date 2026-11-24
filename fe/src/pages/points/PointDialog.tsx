import { X } from 'lucide-react'
import { useId, useLayoutEffect, useRef, type ReactNode } from 'react'

import { cx } from '../../lib/cx'

interface PointDialogProps {
  title: string
  description?: string
  drawer?: boolean
  busy?: boolean
  onDismiss: () => void
  children: ReactNode
}

export function PointDialog({ title, description, drawer, busy, onDismiss, children }: PointDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useLayoutEffect(() => {
    const element = dialog.current!
    element.showModal()
    element.querySelector<HTMLElement>('[data-initial-focus]')?.focus()
    return () => { element.close() }
  }, [])

  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault()
        if (!busy) onDismiss()
      }}
      className={cx(
        'max-h-[calc(100dvh-2rem)] max-w-none overflow-auto bg-surface text-ink backdrop:bg-ink/25',
        drawer
          ? 'inset-y-0 right-0 left-auto m-0 h-dvh max-h-none w-full shadow-drawer open:flex open:flex-col sm:w-120'
          : 'm-auto w-[min(440px,calc(100%_-_2rem))] rounded-sheet shadow-pop',
      )}
    >
      <div className={cx('flex shrink-0 items-start justify-between gap-4 px-5 pt-5 sm:px-6', drawer && 'border-b border-line pb-4')}>
        <div className="min-w-0">
          <h2 id={titleId} className="text-panel wrap-anywhere">{title}</h2>
          {description && <p id={descriptionId} className="mt-1 text-small wrap-anywhere text-ink-2">{description}</p>}
        </div>
        <button
          type="button"
          aria-label="Закрыть"
          disabled={busy}
          onClick={onDismiss}
          className="inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-ctl text-ink-2 hover:bg-hover disabled:opacity-45"
        >
          <X aria-hidden className="size-4.5" strokeWidth={1.75} />
        </button>
      </div>
      {children}
    </dialog>
  )
}
