import { TextQuote } from 'lucide-react'

import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'

/** S3. Суммаризация — docs/screens.md */
export function SummaryPage() {
  return (
    <>
      <PageHeader title="Суммаризация" description="Выжимка отзывов с цитатами: что нравится и на что жалуются" />
      <EmptyState
        icon={TextQuote}
        title="Суммаризация ещё не сформирована"
        text="Сервис соберёт общий вывод и тезисы «Что нравится» и «На что жалуются» с дословными цитатами по выбранным точкам, источникам и периоду."
      />
    </>
  )
}
