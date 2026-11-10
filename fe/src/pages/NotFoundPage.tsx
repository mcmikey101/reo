import { Compass } from 'lucide-react'
import { Link } from 'react-router'

import { buttonClass } from '../components/button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { paths } from '../paths'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Страница не найдена" />
      <EmptyState
        icon={Compass}
        title="Такой страницы нет"
        text="Проверьте адрес или перейдите на дашборд."
        actions={
          <Link to={paths.dashboard} className={buttonClass()}>
            На дашборд
          </Link>
        }
      />
    </>
  )
}
