import { TriangleAlert } from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState, type FormEvent } from 'react'

import { ApiError } from '../../api/client'
import { useSavePoint, type Point, type PointInput } from '../../api/points'
import { buttonClass } from '../../components/button'
import { cx } from '../../lib/cx'
import { PointDialog } from './PointDialog'

const fields = [
  { name: 'name', label: 'Название', limit: 120, hint: 'Внутреннее имя объекта' },
  { name: 'address', label: 'Адрес', limit: 250, hint: 'До 250 символов' },
  { name: 'category', label: 'Категория', limit: 60, hint: 'До 60 символов', placeholder: 'Например, «Кофейня в ТЦ»' },
] as const

type Field = keyof PointInput
type FieldErrors = Partial<Record<Field, string>>
type Draft = Record<Field, string>

function getFieldErrors(error: ApiError): FieldErrors {
  const errors: FieldErrors = {}
  if (typeof error.details !== 'object' || !error.details || !('fields' in error.details) || !Array.isArray(error.details.fields)) {
    return errors
  }
  for (const item of error.details.fields) {
    if (item && typeof item.message === 'string' && fields.some(({ name }) => name === item.field)) {
      errors[item.field as Field] = item.message
    }
  }
  return errors
}

function getDuplicatePoint(details: unknown): string | undefined {
  if (!details || typeof details !== 'object' || !('existing_point' in details)) return
  const point = details.existing_point
  if (!point || typeof point !== 'object' || !('name' in point) || !('address' in point)) return
  if (typeof point.name === 'string' && typeof point.address === 'string') return `${point.name} · ${point.address}`
}

function changedFields(point: Point, input: PointInput): Partial<PointInput> {
  return {
    ...(point.name !== input.name && { name: input.name }),
    ...(point.address !== input.address && { address: input.address }),
    ...(point.category !== input.category && { category: input.category }),
  }
}

interface PointFormProps {
  point?: Point
  onDismiss: () => void
  onSaved: (point: Point, created: boolean) => void
}

export function PointForm({ point, onDismiss, onSaved }: PointFormProps) {
  const initial = { name: point?.name ?? '', address: point?.address ?? '', category: point?.category ?? '' }
  const [draft, setDraft] = useState<Draft>(initial)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [errorMessage, setErrorMessage] = useState('')
  const [duplicate, setDuplicate] = useState<{ message: string; point?: string } | null>(null)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  const focusField = useRef<Field | undefined>(undefined)
  const inputId = useId()
  const mutation = useSavePoint()
  const dirty = fields.some(({ name }) => draft[name] !== initial[name])

  useLayoutEffect(() => {
    if (mutation.isPending || !focusField.current) return
    form.current?.querySelector<HTMLInputElement>(`[name="${focusField.current}"]`)?.focus()
    focusField.current = undefined
  }, [fieldErrors, mutation.isPending])

  function dismiss() {
    if (dirty) setConfirmDiscard(true)
    else onDismiss()
  }

  function showFieldErrors(errors: FieldErrors) {
    focusField.current = fields.find(({ name }) => errors[name])?.name
    setFieldErrors(errors)
  }

  async function save(allowDuplicate: boolean) {
    const input = { name: draft.name.trim(), address: draft.address.trim(), category: draft.category.trim() || null }
    const errors: FieldErrors = {}
    for (const { name, limit } of fields) {
      const value = input[name] ?? ''
      if (!value && name !== 'category') errors[name] = name === 'name' ? 'Укажите название' : 'Укажите адрес'
      else if ([...value].length > limit) errors[name] = `Не больше ${limit} символов`
    }
    setErrorMessage('')
    if (Object.keys(errors).length) {
      showFieldErrors(errors)
      return
    }
    setFieldErrors({})
    try {
      const saved = await mutation.mutateAsync(point
        ? { pointId: point.id, input: changedFields(point, input), allowDuplicate }
        : { input, allowDuplicate })
      onSaved(saved, !point)
    } catch (error) {
      if (error instanceof ApiError && error.code === 'possible_duplicate') {
        setDuplicate({ message: error.message, point: getDuplicatePoint(error.details) })
      } else if (error instanceof ApiError && error.code === 'validation_error') {
        setDuplicate(null)
        showFieldErrors(getFieldErrors(error))
        setErrorMessage(error.message)
      } else {
        setErrorMessage(error instanceof ApiError ? error.message : 'Не удалось сохранить точку. Попробуйте ещё раз.')
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!duplicate && !mutation.isPending) void save(false)
  }

  return (
    <>
      <PointDialog
        drawer
        title={point ? 'Изменить точку' : 'Новая точка'}
        description={point ? point.name : 'Отзывы собираются по точке; источники подключаются после сохранения'}
        busy={mutation.isPending}
        onDismiss={dismiss}
      >
        <form ref={form} noValidate onSubmit={submit} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <fieldset disabled={mutation.isPending} className="flex min-w-0 flex-1 flex-col gap-4.5 px-5 py-4 sm:px-6">
            {fields.map(({ name, label, hint, limit, ...rest }) => {
              const id = `${inputId}-${name}`
              const error = fieldErrors[name]
              return (
                <div key={name} className="flex flex-col gap-1.5">
                  <label htmlFor={id} className="text-small font-semibold">
                    {label}{name === 'category' && <span className="ml-2 text-caption font-normal text-ink-3">необязательно</span>}
                  </label>
                  <input
                    id={id}
                    name={name}
                    type="text"
                    data-initial-focus={name === 'name' ? '' : undefined}
                    required={name !== 'category'}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={`${id}-hint`}
                    value={draft[name]}
                    placeholder={'placeholder' in rest ? rest.placeholder : undefined}
                    onChange={(event) => {
                      const value = event.target.value
                      setDraft((current) => ({ ...current, [name]: value }))
                      setFieldErrors((current) => ({ ...current, [name]: undefined }))
                      setDuplicate(null)
                      setErrorMessage('')
                    }}
                    className={cx('h-11 w-full rounded-ctl border bg-surface px-3 text-body placeholder:text-ink-3 sm:h-9',
                      error ? 'border-neg' : 'border-input-line')}
                  />
                  <div className="flex justify-between gap-2 text-caption">
                    <span id={`${id}-hint`} className={error ? 'text-neg-ink' : 'text-ink-3'}>{error ?? hint}</span>
                    {name === 'name' && <span aria-hidden className="text-ink-3 tabular-nums">{[...draft.name.trim()].length} / {limit}</span>}
                  </div>
                </div>
              )
            })}
            {point && dirty && (
              <p className="rounded-ctl border border-line bg-surface-2 p-3 text-small text-ink-2">
                Изменения применятся после сохранения.
              </p>
            )}
            {duplicate && (
              <div role="alert" className="flex items-start gap-2 rounded-ctl border border-warn-line bg-warn-tint p-3 text-small text-warn-ink">
                <TriangleAlert aria-hidden className="size-4 shrink-0" strokeWidth={1.75} />
                <div className="min-w-0 wrap-anywhere">
                  <p className="font-semibold">Возможный дубль</p>
                  <p>{duplicate.message}</p>
                  {duplicate.point && <p className="mt-1">{duplicate.point}</p>}
                </div>
              </div>
            )}
            {errorMessage && <p role="alert" className="rounded-ctl bg-neg-tint p-3 text-small text-neg-ink">{errorMessage}</p>}
          </fieldset>
          <footer className="sticky bottom-0 flex flex-wrap justify-end gap-2 border-t border-line bg-surface px-5 py-4 sm:px-6">
            <button type="button" className={buttonClass({ kind: 'ghost' })} onClick={dismiss} disabled={mutation.isPending}>
              Отмена
            </button>
            {duplicate ? (
              <button type="button" className={buttonClass({ kind: 'primary' })} onClick={() => void save(true)} disabled={mutation.isPending}>
                {mutation.isPending ? 'Сохраняем…' : 'Сохранить всё равно'}
              </button>
            ) : (
              <button type="submit" className={buttonClass({ kind: 'primary' })} disabled={mutation.isPending}>
                {mutation.isPending ? 'Сохраняем…' : 'Сохранить'}
              </button>
            )}
          </footer>
        </form>
      </PointDialog>
      {confirmDiscard && (
        <PointDialog title="Закрыть без сохранения?" description="Введённые изменения будут потеряны." onDismiss={() => setConfirmDiscard(false)}>
          <div className="flex flex-wrap justify-end gap-2 px-5 py-5 sm:px-6">
            <button type="button" className={buttonClass()} onClick={() => setConfirmDiscard(false)} data-initial-focus>
              Продолжить редактирование
            </button>
            <button type="button" className={buttonClass({ kind: 'danger' })} onClick={onDismiss}>Закрыть без сохранения</button>
          </div>
        </PointDialog>
      )}
    </>
  )
}
