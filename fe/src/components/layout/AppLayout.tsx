import { Outlet, ScrollRestoration } from 'react-router'

import { useSidebarCollapsed } from '../../state/useSidebarCollapsed'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

/**
 * Каркас всех экранов: шапка и меню закреплены, прокручивается страница.
 * Рабочая область — отступы 24 px, снизу 48 px, между блоками 16 px.
 */
export function AppLayout() {
  const { collapsed, toggle } = useSidebarCollapsed()

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only rounded-ctl bg-surface px-3 py-2 shadow-pop focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
      >
        Перейти к содержимому
      </a>
      <Header />
      <div className="flex">
        <Sidebar collapsed={collapsed} onToggle={toggle} />
        {/* tabIndex — чтобы ссылка «Перейти к содержимому» переводила сюда фокус */}
        <main id="main" tabIndex={-1} className="flex min-w-0 flex-1 flex-col gap-4 px-6 pt-6 pb-12 outline-none">
          <Outlet />
        </main>
      </div>
      <ScrollRestoration />
    </div>
  )
}
