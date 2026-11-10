import { Plug } from 'lucide-react'

import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'

/** M2. Источники — docs/screens.md */
export function SourcesPage() {
  return (
    <>
      <PageHeader title="Источники" description="Связи «точка × площадка», импорт CSV и статусы сбора" />
      <EmptyState
        icon={Plug}
        title="Источников пока нет"
        text="Здесь появятся подключённые площадки и импорты CSV: статус, число отзывов и время последнего сбора."
      />
    </>
  )
}
