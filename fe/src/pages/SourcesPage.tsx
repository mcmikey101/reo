import { Plug, Upload } from 'lucide-react'
import { useState } from 'react'

import { buttonClass } from '../components/button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { CsvImportDialog } from './sources/CsvImportDialog'
import { CsvImportReport, type CsvReport } from './sources/CsvImportReport'

/** M2. Источники — docs/screens.md */
export function SourcesPage() {
  const [importOpen, setImportOpen] = useState(false)
  const [report, setReport] = useState<CsvReport | null>(null)

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
      {importOpen && (
        <CsvImportDialog
          onClose={() => setImportOpen(false)}
          onImported={(nextReport) => {
            setReport(nextReport)
            setImportOpen(false)
          }}
        />
      )}
    </>
  )
}
