import { ChartNoAxesColumnIncreasing, LoaderCircle } from 'lucide-react'

import { useImportAnalysis, type ImportAnalysis } from '../../api/importAnalysis'
import { buttonClass } from '../../components/button'

const formatIndex = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 })

function AnalysisMetrics({ result }: { result: NonNullable<ImportAnalysis['result']> }) {
  const { sentiment_counts: counts, satisfaction_index: index } = result
  const sentiments = [
    { label: 'Позитивные', count: counts.positive, dot: 'bg-pos' },
    { label: 'Нейтральные', count: counts.neutral, dot: 'bg-neu' },
    { label: 'Негативные', count: counts.negative, dot: 'bg-neg' },
  ]

  return (
    <div className="grid gap-3 @lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <dl className="rounded-card border border-line bg-surface-2 p-3">
        <dt className="text-small font-medium text-ink-2">Индекс удовлетворённости</dt>
        <dd className="mt-2 text-panel tabular-nums">
          {index === null ? 'Недостаточно данных' : (
            <>{formatIndex.format(index)} <span className="text-small font-normal text-ink-2">из 100</span></>
          )}
        </dd>
      </dl>
      <div className="rounded-card border border-line bg-surface-2 p-3">
        <h4 className="text-small font-medium text-ink-2">Распределение тональности</h4>
        <dl className="mt-2 grid gap-2 @sm:grid-cols-3">
          {sentiments.map(({ label, count, dot }) => (
            <div key={label} className="flex min-w-0 items-center justify-between gap-2 @sm:block">
              <dt className="flex items-center gap-1.5 text-caption text-ink-2">
                <span aria-hidden className={`size-2 shrink-0 rounded-full ${dot}`} />
                {label}
              </dt>
              <dd className="text-panel tabular-nums @sm:mt-1">{count.toLocaleString('ru-RU')}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}

export function ImportAnalysisPanel({ importId, restored }: { importId: string; restored: boolean }) {
  const { status, start } = useImportAnalysis(importId, restored)
  const data = status.data
  const running = data?.status === 'running'
  const checking = restored && !data && !status.isError
  const result = data?.result
  const analysisError = data?.error

  return (
    <section aria-labelledby="import-analysis-title" className="@container flex flex-col gap-3 border-t border-line pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="import-analysis-title" className="flex items-center gap-2 text-widget">
          <ChartNoAxesColumnIncreasing aria-hidden className="size-4" strokeWidth={1.75} />
          Анализ отзывов
        </h3>
        {!running && !checking && !status.isError && data?.status !== 'done' && (
          <button
            type="button"
            className={buttonClass({ kind: 'primary' })}
            disabled={start.isPending}
            onClick={() => start.mutate()}
          >
            {data?.status === 'error' ? 'Повторить анализ' : 'Запустить анализ'}
          </button>
        )}
      </div>

      <output className={start.isPending || running || checking || data?.status === 'done' ? 'flex items-center gap-2 text-small text-ink-2' : 'sr-only'}>
        {checking && 'Проверяем статус анализа…'}
        {start.isPending && <><LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />Запускаем анализ…</>}
        {!start.isPending && running && !status.isError && (
          <><LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />Анализ выполняется…</>
        )}
        {data?.status === 'done' && 'Анализ завершён'}
      </output>

      {start.error && <p role="alert" className="rounded-ctl bg-neg-tint p-3 text-small text-neg-ink">{start.error.message}</p>}
      {status.isError && (
        <div className="flex flex-wrap items-center gap-2">
          <p role="alert" className="text-small text-neg-ink">Не удалось проверить статус анализа. {status.error.message}</p>
          <button type="button" className={buttonClass({ size: 's' })} disabled={status.isFetching} onClick={() => void status.refetch()}>
            Проверить статус
          </button>
        </div>
      )}
      {analysisError && (
        <p role="alert" className="rounded-ctl bg-warn-tint p-3 text-small text-warn-ink">
          {analysisError.message}{result?.satisfaction_index != null && ' Ниже — результат по обработанным отзывам.'}
        </p>
      )}
      {result && <AnalysisMetrics result={result} />}
    </section>
  )
}
