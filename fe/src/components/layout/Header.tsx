import { UserRound } from 'lucide-react'
import { Link } from 'react-router'

import { paths } from '../../paths'
import { HealthIndicator } from '../HealthIndicator'
import { BrandMark } from './BrandMark'

/** Шапка 56 px: логотип над меню, индикатор состояния и профиль справа */
export function Header() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface">
      <div className="flex h-full w-58 shrink-0 items-center pr-4 pl-5">
        <Link to={paths.dashboard} className="flex items-center gap-2.5 rounded-ctl text-ink">
          <BrandMark className="size-6.5" />
          <span className="text-brand">reo</span>
        </Link>
      </div>

      <div className="flex-1" />

      <HealthIndicator />

      {/* Меню профиля с выходом появится вместе со входом (E10). Пока — значок без действий. */}
      <div className="pr-4">
        <span aria-hidden className="flex size-8.5 items-center justify-center rounded-full bg-avatar">
          <UserRound className="size-4 text-ink-2" strokeWidth={1.75} />
        </span>
      </div>
    </header>
  )
}
