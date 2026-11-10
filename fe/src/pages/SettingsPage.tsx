import { Settings } from 'lucide-react'

import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'

/** P1. Настройки — docs/screens.md */
export function SettingsPage() {
  return (
    <>
      <PageHeader title="Настройки" description="Профиль и организация" />
      <EmptyState
        icon={Settings}
        title="Настройки пока недоступны"
        text="Здесь можно будет изменить имя в профиле, а также название и отрасль организации."
      />
    </>
  )
}
