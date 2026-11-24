import { Plug, Upload } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { buttonClass } from '../components/button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { CsvImportDialog } from './sources/CsvImportDialog'
import { CsvImportReport, type CsvReport } from './sources/CsvImportReport'

/** M2. Источники — docs/screens.md */
export function SourcesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const linkedPointId = searchParams.get('point_id') || undefined
  const [importOpen, setImportOpen] = useState(false)
  const [report, setReport] = useState<CsvReport | null>(null)

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
        ? <CsvImportReport key={report.result.import_id} report={report} />
        : <EmptyState icon={Plug} title="Импорт отзывов" text="Загрузите отзывы из CSV для одной из ваших точек." />}
      {(importOpen || linkedPointId) && (
        <CsvImportDialog
          key={linkedPointId}
          initialPointId={linkedPointId}
          onClose={closeImport}
          onImported={(nextReport) => {
            setReport(nextReport)
            closeImport()
          }}
        />
      )}
    </>
  )
}
