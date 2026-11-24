import { CircleCheck, TriangleAlert } from 'lucide-react'
import { useLayoutEffect, useRef, useState } from 'react'

import type { CsvImportResult } from '../../api/csvImport'
import { buttonClass } from '../../components/button'

const ERROR_PAGE_SIZE = 50

export interface CsvReport {
  result: CsvImportResult
  pointName: string
  fileName: string
}

export function CsvImportReport({ report }: { report: CsvReport }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const [visibleErrors, setVisibleErrors] = useState(ERROR_PAGE_SIZE)
  const { total, imported, duplicates, rejected, errors } = report.result
  const stats = [
    { label: 'Всего', count: total, className: 'bg-surface-2' },
    { label: 'Добавлено', count: imported, className: 'bg-pos-tint text-pos-ink' },
    { label: 'Дубли', count: duplicates, className: 'bg-surface-2' },
    { label: 'Отклонено', count: rejected, className: rejected ? 'bg-warn-tint text-warn-ink' : 'bg-surface-2' },
  ]
  const StatusIcon = rejected ? TriangleAlert : CircleCheck

  useLayoutEffect(() => { heading.current?.focus() }, [])

  return (
    <section aria-labelledby="csv-report-title" className="flex max-w-200 flex-col gap-4 rounded-sheet border border-line bg-surface p-4 sm:p-6">
      <div className="flex items-start gap-3">
        <StatusIcon aria-hidden className={rejected ? 'size-6 shrink-0 text-warn-ink' : 'size-6 shrink-0 text-pos-ink'} strokeWidth={1.75} />
        <div className="min-w-0">
          <h2 ref={heading} id="csv-report-title" tabIndex={-1} className="text-panel">
            {imported ? 'Импорт завершён' : 'Нет новых отзывов'}
          </h2>
          <p className="mt-1 text-small wrap-anywhere text-ink-2">{report.pointName} · {report.fileName}</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {stats.map(({ label, count, className }) => (
          <div key={label} className={`min-w-0 rounded-ctl p-2 sm:p-3 ${className}`}>
            <dt className="text-small wrap-anywhere">{label}</dt>
            <dd className="text-panel tabular-nums">{count.toLocaleString('ru-RU')}</dd>
          </div>
        ))}
      </dl>
      {errors.length > 0 && (
        <div className="min-w-0">
          <h3 className="mb-2 text-widget">Ошибки по строкам</h3>
          <table className="w-full table-fixed border-collapse text-left text-small">
            <thead className="text-ink-2">
              <tr>
                <th scope="col" className="w-21 border-b border-line p-2 font-medium">Строка</th>
                <th scope="col" className="border-b border-line p-2 font-medium">Причина</th>
              </tr>
            </thead>
            <tbody>
              {errors.slice(0, visibleErrors).map(({ row, message }) => (
                <tr key={row}>
                  <th scope="row" className="border-b border-line-soft p-2 align-top font-medium tabular-nums">{row}</th>
                  <td className="border-b border-line-soft p-2 wrap-anywhere">{message}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibleErrors < errors.length && (
            <button type="button" className={`mt-3 ${buttonClass({ size: 's' })}`} onClick={() => setVisibleErrors((count) => count + ERROR_PAGE_SIZE)}>
              Показать ещё ошибки
            </button>
          )}
        </div>
      )}
    </section>
  )
}
