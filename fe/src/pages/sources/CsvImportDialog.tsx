import { FileSpreadsheet, LoaderCircle, Upload, X } from 'lucide-react'
import { useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { MAX_CSV_BYTES, useCsvImport } from '../../api/csvImport'
import { usePoint, usePoints } from '../../api/points'
import { buttonClass } from '../../components/button'
import { paths } from '../../paths'
import type { CsvReport } from './CsvImportReport'

const CSV_EXAMPLE = 'date,text,rating\n2026-11-20,"Вкусный кофе, быстро обслужили",5\n2026-11-21,Уютное место,'

interface CsvImportDialogProps {
  initialPointId?: string
  onClose: () => void
  onImported: (report: CsvReport) => void
}

export function CsvImportDialog({ initialPointId, onClose, onImported }: CsvImportDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const submitInProgress = useRef(false)
  const [pointId, setPointId] = useState(initialPointId ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState('')
  const pointList = usePoints('')
  const upload = useCsvImport()
  const listedPoints = pointList.data?.pages.flatMap((page) => page.items) ?? []
  const needsLinkedPoint = initialPointId !== undefined && !pointList.isPending &&
    !listedPoints.some((point) => point.id === initialPointId)
  const linkedPoint = usePoint(needsLinkedPoint ? initialPointId : undefined)
  const points = linkedPoint.data ? [linkedPoint.data, ...listedPoints] : listedPoints
  const selectedPoint = points.find((point) => point.id === pointId)
  const busy = upload.isPending

  useLayoutEffect(() => {
    const element = dialog.current!
    element.showModal()
    return () => { element.close() }
  }, [])

  function selectFile(nextFile: File) {
    upload.reset()
    if (nextFile.size === 0 || nextFile.size > MAX_CSV_BYTES) {
      setFile(null)
      setFileError(nextFile.size === 0 ? 'Файл пуст. Выберите CSV с отзывами.' : 'Размер файла превышает 10 МиБ.')
      return
    }
    setFile(nextFile)
    setFileError('')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedPoint || !file || submitInProgress.current) return
    submitInProgress.current = true
    try {
      const result = await upload.mutateAsync({ pointId: selectedPoint.id, file })
      onImported({ result, pointName: selectedPoint.name, fileName: file.name })
    } catch {
      // TanStack Query сохраняет причину в upload.error.
    } finally {
      submitInProgress.current = false
    }
  }

  return (
    <dialog
      ref={dialog}
      aria-labelledby="csv-import-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!submitInProgress.current) onClose()
      }}
      className="m-auto h-dvh max-h-none w-full max-w-none bg-surface text-ink backdrop:bg-ink/25 sm:h-auto sm:max-h-[calc(100dvh-2rem)] sm:w-160 sm:max-w-[calc(100%_-_2rem)] sm:rounded-sheet sm:shadow-pop"
    >
      <form onSubmit={(event) => void submit(event)} className="flex h-full max-h-[inherit] flex-col">
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-line px-4 py-4 sm:px-6">
          <h2 id="csv-import-title" className="text-panel">Импорт отзывов из CSV</h2>
          <button type="button" aria-label="Закрыть" className={buttonClass({ kind: 'ghost', size: 's' })} disabled={busy} onClick={onClose}>
            <X aria-hidden className="size-4.5" strokeWidth={1.75} />
          </button>
        </header>

        <fieldset disabled={busy} className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6">
          <div className="flex min-w-0 flex-col gap-2">
            <label htmlFor="csv-import-point" className="text-small font-semibold">Точка для всего файла</label>
            <select
              id="csv-import-point"
              required
              disabled={points.length === 0}
              value={selectedPoint?.id ?? ''}
              onChange={(event) => { setPointId(event.target.value); upload.reset() }}
              className="h-11 w-full min-w-0 rounded-ctl border border-input-line bg-surface px-3 text-body disabled:bg-surface-2 sm:h-9"
            >
              <option value="">Выберите точку</option>
              {points.map((point) => <option key={point.id} value={point.id}>{point.name} · {point.address}</option>)}
            </select>
            {pointList.isPending && <output className="text-small text-ink-2">Загружаем точки…</output>}
            {linkedPoint.isLoading && <output className="text-small text-ink-2">Загружаем точку по ссылке…</output>}
            {linkedPoint.isError && (
              <p role="alert" className="text-small text-neg-ink">Не удалось загрузить точку по ссылке. Можно выбрать другую точку.</p>
            )}
            {pointList.isError && listedPoints.length === 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <p role="alert" className="text-small text-neg-ink">Не удалось загрузить точки. {pointList.error.message}</p>
                <button type="button" className={buttonClass({ size: 's' })} onClick={() => void pointList.refetch()}>Повторить</button>
              </div>
            )}
            {pointList.isSuccess && !linkedPoint.isLoading && points.length === 0 && (
              <p className="text-small text-ink-2">
                Сначала добавьте точку на экране <Link to={paths.points} className="font-medium text-ink underline">«Точки»</Link>.
              </p>
            )}
            {pointList.hasNextPage && (
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" className={buttonClass({ size: 's' })} disabled={pointList.isFetching} onClick={() => void pointList.fetchNextPage()}>
                  {pointList.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё точки'}
                </button>
                {pointList.isFetchNextPageError && <p role="alert" className="text-small text-neg-ink">Не удалось загрузить остальные точки.</p>}
              </div>
            )}
          </div>

          <div
            className="flex flex-col items-center gap-2 rounded-card border border-dashed border-line-strong bg-surface-2 px-3 py-5 text-center"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              const firstFile = event.dataTransfer.files.item(0)
              if (firstFile && !submitInProgress.current) selectFile(firstFile)
            }}
          >
            <Upload aria-hidden className="size-6 text-ink-2" strokeWidth={1.75} />
            <p className="text-small text-ink-2">Выберите CSV-файл или перетащите его сюда</p>
            <input
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              aria-label="CSV-файл"
              aria-describedby="csv-import-format"
              aria-invalid={fileError ? true : undefined}
              tabIndex={-1}
              className="sr-only"
              onChange={(event) => {
                const firstFile = event.currentTarget.files?.[0]
                if (firstFile) selectFile(firstFile)
                event.currentTarget.value = ''
              }}
            />
            <button type="button" className={buttonClass()} onClick={() => fileInput.current?.click()}>
              {file ? 'Заменить файл' : 'Выбрать файл'}
            </button>
          </div>
          {file && (
            <div className="flex min-w-0 items-center gap-2 rounded-ctl border border-line px-3 py-2">
              <FileSpreadsheet aria-hidden className="size-4 shrink-0 text-pos-ink" strokeWidth={1.75} />
              <span className="min-w-0 flex-1 text-small wrap-anywhere">{file.name}</span>
              <button
                type="button"
                aria-label="Убрать файл"
                className={buttonClass({ kind: 'ghost', size: 's' })}
                onClick={() => { setFile(null); upload.reset() }}
              >
                <X aria-hidden className="size-4" strokeWidth={1.75} />
              </button>
            </div>
          )}
          {fileError && <p role="alert" className="text-small text-neg-ink">{fileError}</p>}

          <div id="csv-import-format" className="flex flex-col gap-2 rounded-card bg-surface-2 p-3">
            <h3 className="text-small font-semibold">Формат файла</h3>
            <p className="text-small text-ink-2">
              UTF-8, до 10 МиБ. Разделитель — запятая. Дата в формате YYYY-MM-DD, текст обязателен,
              оценка от 1 до 5 или пустая.
            </p>
            <pre className="whitespace-pre-wrap text-caption wrap-anywhere"><code>{CSV_EXAMPLE}</code></pre>
          </div>
          {upload.error && <p role="alert" className="rounded-ctl bg-neg-tint p-3 text-small text-neg-ink">{upload.error.message}</p>}
        </fieldset>

        <footer className="flex shrink-0 flex-wrap justify-end gap-2 border-t border-line px-4 py-4 sm:px-6">
          <output className="sr-only">{busy ? 'Импортируем отзывы…' : ''}</output>
          <button type="button" className={buttonClass({ kind: 'ghost' })} disabled={busy} onClick={onClose}>Отмена</button>
          <button type="submit" className={buttonClass({ kind: 'primary' })} disabled={!selectedPoint || !file || busy}>
            {busy && <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />}
            {busy ? 'Импортируем…' : 'Импортировать'}
          </button>
        </footer>
      </form>
    </dialog>
  )
}
