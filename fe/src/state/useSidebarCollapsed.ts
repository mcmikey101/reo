import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'reo.sidebar.collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

/** Свёрнуто ли боковое меню. Выбор запоминается в браузере. */
export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(readCollapsed)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0')
    } catch {
      // Хранилище недоступно (приватный режим) — меню просто не запомнит выбор
    }
  }, [collapsed])

  const toggle = useCallback(() => setCollapsed((value) => !value), [])

  return { collapsed, toggle }
}
