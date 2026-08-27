// frontend/lib/api/client.ts
// Central fetch client. All API calls go through here.
// Reads NEXT_PUBLIC_API_URL and attaches Authorization header automatically.

import { clearAuthSession, getAuthToken } from '@/lib/auth-session'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

function buildHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Request-ID': `fe-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    ...extra,
  }
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearAuthSession()
    if (typeof window !== 'undefined') {
      window.location.href = '/sign-in'
    }
    throw new ApiClientError(401, 'Authentication required')
  }

  if (!res.ok) {
    let body: unknown
    try { body = await res.json() } catch { body = await res.text().catch(() => '') }
    const msg =
      (typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as Record<string, unknown>).detail)
        : null) || res.statusText || `HTTP ${res.status}`
    throw new ApiClientError(res.status, msg, body)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {}
): Promise<T> {
  const { params, ...rest } = options
  let url = `${BASE_URL}${path}`

  if (params) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.append(k, String(v))
    }
    const qsStr = qs.toString()
    if (qsStr) url += '?' + qsStr
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000)

  try {
    const res = await fetch(url, {
      ...rest,
      headers: buildHeaders(rest.headers as Record<string, string>),
      signal: controller.signal,
    })
    return handleResponse<T>(res)
  } catch (err) {
    if (err instanceof ApiClientError) throw err
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiClientError(0, 'Request timed out')
    }
    throw new ApiClientError(0, err instanceof Error ? err.message : 'Network error')
  } finally {
    clearTimeout(timeoutId)
  }
}

export const isApiMode = () =>
  process.env.NEXT_PUBLIC_DATA_MODE === 'api'
