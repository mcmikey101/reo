import { MapPin } from 'lucide-react'

import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'

/** M1. Точки — docs/screens.md, API — docs/api-contract.md */
export function PointsPage() {
  return (
    <>
      <PageHeader title="Точки" description="Объекты, по которым собираются отзывы" />
      <EmptyState
        icon={MapPin}
        title="Точек пока нет"
        text="Точка — кофейня, ресторан или другой объект, по которому собираются отзывы."
      />
    </>
  )
}
