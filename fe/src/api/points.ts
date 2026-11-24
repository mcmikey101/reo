import { skipToken, useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from '@tanstack/react-query'

import { ApiError, apiGet, apiRequest } from './client'

export interface PointInput {
  name: string
  address: string
  category: string | null
}

export interface Point extends PointInput {
  id: string
  sources_count: number
  data_status: string
  created_at: string
  updated_at: string
}

interface PointList {
  items: Point[]
  total: number
  limit: number
  offset: number
}

export const pointsKey = ['points'] as const
const pointListsKey = [...pointsKey, 'list'] as const
const pointKey = (id: string | undefined) => [...pointsKey, 'detail', id] as const

function isPoint(value: unknown): value is Point {
  if (typeof value !== 'object' || !value) return false
  const point = value as Partial<Point>
  return (
    typeof point.id === 'string' &&
    typeof point.name === 'string' &&
    typeof point.address === 'string' &&
    (point.category === null || typeof point.category === 'string') &&
    typeof point.sources_count === 'number' &&
    typeof point.data_status === 'string' &&
    typeof point.created_at === 'string' &&
    typeof point.updated_at === 'string'
  )
}

function parsePoint(value: unknown): Point {
  if (!isPoint(value)) {
    throw new ApiError('API вернул точку в неожиданном формате', { kind: 'parse' })
  }
  return value
}

function parsePointList(value: unknown): PointList {
  if (typeof value === 'object' && value) {
    const { items, total, limit, offset } = value as Partial<PointList>
    if (Array.isArray(items) && items.every(isPoint) &&
        typeof total === 'number' && Number.isSafeInteger(total) && total >= 0 &&
        typeof limit === 'number' && Number.isSafeInteger(limit) && limit > 0 &&
        typeof offset === 'number' && Number.isSafeInteger(offset) && offset >= 0) {
      return { items, total, limit, offset }
    }
  }
  throw new ApiError('API вернул список точек в неожиданном формате', { kind: 'parse' })
}

export function usePoints(query: string) {
  return useInfiniteQuery({
    queryKey: [...pointListsKey, query],
    initialPageParam: 0,
    queryFn: async ({ signal, pageParam }) => {
      const params = new URLSearchParams({ limit: '50', offset: String(pageParam) })
      if (query) params.set('q', query)
      return parsePointList(await apiGet(`/points?${params}`, { signal }))
    },
    getNextPageParam: ({ offset, limit, total, items }) =>
      items.length && offset + limit < total ? offset + limit : undefined,
    retry: false,
  })
}

export function usePoint(id?: string) {
  return useQuery({
    queryKey: pointKey(id),
    queryFn: id
      ? async ({ signal }) => parsePoint(await apiGet(`/points/${encodeURIComponent(id)}`, { signal }))
      : skipToken,
    retry: false,
  })
}

type SavePoint = { allowDuplicate?: boolean } & (
  | { pointId?: undefined; input: PointInput }
  | { pointId: string; input: Partial<PointInput> }
)

export function useSavePoint() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ pointId, input, allowDuplicate }: SavePoint) => {
      const path = pointId ? `/points/${encodeURIComponent(pointId)}` : '/points'
      const result = await apiRequest(path + (allowDuplicate ? '?allow_duplicate=true' : ''), {
        method: pointId ? 'PATCH' : 'POST',
        body: input,
      })
      return parsePoint(result)
    },
    onSuccess: () => { void client.invalidateQueries({ queryKey: pointsKey }) },
  })
}

export function useDeletePoint() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      try {
        await apiRequest(`/points/${encodeURIComponent(id)}`, { method: 'DELETE' })
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 404)) throw error
      }
    },
    onSuccess: async (_, id) => {
      await client.cancelQueries({ queryKey: pointsKey })
      client.removeQueries({ queryKey: pointKey(id), exact: true })
      client.setQueriesData<InfiniteData<PointList>>({ queryKey: pointListsKey }, (data) => {
        if (!data?.pages.some(({ items }) => items.some((point) => point.id === id))) return data
        return {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.filter((point) => point.id !== id),
            total: page.total - 1,
          })),
        }
      })
      void client.invalidateQueries({ queryKey: pointsKey })
    },
  })
}
