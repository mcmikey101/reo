import { LayoutDashboard, MapPin, Plug, Settings, TextQuote, type LucideIcon } from 'lucide-react'

import { paths } from '../../paths'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

/**
 * Пункты бокового меню по макету. Новый экран: маршрут в src/router.tsx + пункт здесь.
 * «Область анализа» (S1) не добавлена: отдельный экран или панель на дашборде — ещё не решено (docs/screens.md).
 */
export const navGroups: NavGroup[] = [
  {
    title: 'Аналитика',
    items: [
      { to: paths.dashboard, label: 'Дашборд', icon: LayoutDashboard },
      { to: paths.summary, label: 'Суммаризация', icon: TextQuote },
    ],
  },
  {
    title: 'Данные',
    items: [
      { to: paths.points, label: 'Точки', icon: MapPin },
      { to: paths.sources, label: 'Источники', icon: Plug },
    ],
  },
]

/** Пункт внизу меню, над кнопкой «Свернуть меню» */
export const settingsItem: NavItem = { to: paths.settings, label: 'Настройки', icon: Settings }
