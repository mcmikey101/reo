import { LayoutDashboard } from 'lucide-react'

import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'

/** S2. Дашборд — docs/screens.md */
export function DashboardPage() {
  return (
    <>
      <PageHeader title="Дашборд" description="Показатели по выбранным точкам, источникам и периоду" />
      <EmptyState
        icon={LayoutDashboard}
        title="Данных для анализа пока нет"
        text="Когда появятся точки и отзывы, здесь будут индекс удовлетворённости, тональность, проблемы клиентов и таблица точек."
      />
    </>
  )
}
