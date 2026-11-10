import { createBrowserRouter, Navigate, type RouteObject } from 'react-router'

import { AppLayout } from './components/layout/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PointsPage } from './pages/PointsPage'
import { RouteErrorPage } from './pages/RouteErrorPage'
import { SettingsPage } from './pages/SettingsPage'
import { SourcesPage } from './pages/SourcesPage'
import { SummaryPage } from './pages/SummaryPage'
import { paths } from './paths'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      // После входа пользователь попадает на дашборд (docs/screens.md, «Навигация»)
      { index: true, element: <Navigate to={paths.dashboard} replace /> },
      {
        // Ошибка экрана показывается внутри каркаса, шапка и меню остаются
        errorElement: <RouteErrorPage />,
        children: [
          { path: paths.dashboard, element: <DashboardPage /> },
          { path: paths.summary, element: <SummaryPage /> },
          { path: paths.points, element: <PointsPage /> },
          { path: paths.sources, element: <SourcesPage /> },
          { path: paths.settings, element: <SettingsPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
