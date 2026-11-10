import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useId } from 'react'
import { NavLink } from 'react-router'

import { cx } from '../../lib/cx'
import { navGroups, settingsItem, type NavGroup, type NavItem } from './navigation'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

/** Общий вид пункта меню: высота 38 px, иконка 18 px, отступы по макету */
function itemClass(active: boolean, collapsed: boolean): string {
  return cx(
    'relative flex h-9.5 w-full cursor-pointer items-center gap-2.5 rounded-ctl text-body transition-colors',
    collapsed ? 'justify-center' : 'px-2.5',
    active ? 'bg-nav-active font-semibold text-ink' : 'text-ink-2 hover:bg-hover hover:text-ink',
  )
}

function SidebarLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) => itemClass(isActive, collapsed)}
    >
      {({ isActive }) => (
        <>
          {isActive && <span aria-hidden className="absolute top-2.25 -left-3 h-5 w-0.75 rounded-r-[3px] bg-ink" />}
          <Icon aria-hidden className="size-4.5 shrink-0" strokeWidth={1.75} />
          <span className={collapsed ? 'sr-only' : 'truncate'}>{item.label}</span>
        </>
      )}
    </NavLink>
  )
}

function SidebarGroup({ group, collapsed }: { group: NavGroup; collapsed: boolean }) {
  const titleId = useId()
  return (
    <div className="flex flex-col gap-0.5">
      {/* Высота строки сохраняется и в свёрнутом меню, чтобы иконки не прыгали */}
      <div className="flex h-5.5 items-start justify-center px-2.5">
        {collapsed && <span aria-hidden className="mt-2 h-px w-4 bg-line" />}
        <span id={titleId} className={collapsed ? 'sr-only' : 'w-full text-caption text-ink-3'}>
          {group.title}
        </span>
      </div>
      <ul aria-labelledby={titleId} className="flex flex-col gap-0.5">
        {group.items.map((item) => (
          <li key={item.to}>
            <SidebarLink item={item} collapsed={collapsed} />
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Боковое меню: 232 px, сворачивается до 64 px */
export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose
  const toggleLabel = collapsed ? 'Развернуть меню' : 'Свернуть меню'

  return (
    <aside
      id="sidebar"
      className={cx(
        'sticky top-14 h-[calc(100dvh-3.5rem)] shrink-0 overflow-x-hidden overflow-y-auto border-r border-line bg-surface px-3 py-4 whitespace-nowrap transition-[width] duration-150 motion-reduce:transition-none',
        collapsed ? 'w-16' : 'w-58',
      )}
    >
      <nav aria-label="Основное меню" className="flex h-full flex-col justify-between gap-6">
        <div className="flex flex-col gap-6">
          {navGroups.map((group) => (
            <SidebarGroup key={group.title} group={group} collapsed={collapsed} />
          ))}
        </div>

        <div className="flex flex-col gap-0.5 border-t border-line pt-4">
          <SidebarLink item={settingsItem} collapsed={collapsed} />
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={!collapsed}
            aria-controls="sidebar"
            title={collapsed ? toggleLabel : undefined}
            className={itemClass(false, collapsed)}
          >
            <ToggleIcon aria-hidden className="size-4.5 shrink-0" strokeWidth={1.75} />
            <span className={collapsed ? 'sr-only' : 'truncate'}>{toggleLabel}</span>
          </button>
        </div>
      </nav>
    </aside>
  )
}
