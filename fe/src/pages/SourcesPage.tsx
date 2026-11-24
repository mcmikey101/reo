import { useQueryClient } from '@tanstack/react-query'
import { Plug, Upload } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { buttonClass } from '../components/button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { saveLastImportReport, useLastImportReport } from '../state/lastImportReport'
import { CsvImportDialog } from './sources/CsvImportDialog'
import { CsvImportReport } from './sources/CsvImportReport'

/** M2. Источники — docs/screens.md */
export function SourcesPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const linkedPointId = searchParams.get('point_id') || undefined
  const [importOpen, setImportOpen] = useState(false)
  const { data: report } = useLastImportReport()
  const [restored, setRestored] = useState(() => Boolean(report))

  function closeImport() {
    setImportOpen(false)
    if (linkedPointId) {
      const nextSearchParams = new URLSearchParams(searchParams)
      nextSearchParams.delete('point_id')
      setSearchParams(nextSearchParams, { replace: true })
    }
  }

  return (
    <>
      <PageHeader
        title="Источники"
        description="Загрузка отзывов по точкам"
        actions={
          <button type="button" className={buttonClass({ kind: 'primary' })} onClick={() => setImportOpen(true)}>
            <Upload aria-hidden className="size-4" strokeWidth={1.75} />
            Импорт CSV
          </button>
        }
      />
      {report
        ? <CsvImportReport key={report.result.import_id} report={report} restored={restored} />
        : <EmptyState icon={Plug} title="Импорт отзывов" text="Загрузите отзывы из CSV для одной из ваших точек." />}
      {(importOpen || linkedPointId) && (
        <CsvImportDialog
          key={linkedPointId}
          initialPointId={linkedPointId}
          onClose={closeImport}
          onImported={(nextReport) => {
            saveLastImportReport(queryClient, nextReport)
            setRestored(false)
            closeImport()
          }}
        />
      )}
    </>
  )
}
