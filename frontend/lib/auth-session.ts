'use client'

export type AuthSession = {
  accessToken: string
  tokenType: string
  merchantId: string
  name: string
  email: string
}

const SESSION_KEY = 'payback-auth-session'
const LEGACY_DEMO_KEY = 'payback-demo-session'

export function getAuthSession(): AuthSession | null {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(SESSION_KEY)
  if (raw) {
    try {
      return JSON.parse(raw) as AuthSession
    } catch {
      return null
    }
  }
  // Fallback check for legacy demo session
  const legacy = window.localStorage.getItem(LEGACY_DEMO_KEY)
  if (legacy) {
    try {
      const parsed = JSON.parse(legacy)
      return {
        accessToken: '',
        tokenType: 'bearer',
        merchantId: 'merchant_default',
        name: parsed.name || 'Demo Merchant',
        email: parsed.email || 'merchant@payback.demo',
      }
    } catch {
      return null
    }
  }
  return null
}

export function getAuthToken(): string | null {
  const session = getAuthSession()
  return session ? session.accessToken : null
}

export function setAuthSession(session: AuthSession) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  // Keep legacy key in sync for backwards compatibility
  window.localStorage.setItem(
    LEGACY_DEMO_KEY,
    JSON.stringify({ name: session.name, email: session.email })
  )
}

export function clearAuthSession() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(SESSION_KEY)
  window.localStorage.removeItem(LEGACY_DEMO_KEY)
}

// Re-export demo session helpers for backwards compatibility
export type DemoSession = { email: string; name: string }
export function getDemoSession(): DemoSession | null {
  const s = getAuthSession()
  if (!s) return null
  return { email: s.email, name: s.name }
}

export function setDemoSession(session: DemoSession) {
  setAuthSession({
    accessToken: '',
    tokenType: 'bearer',
    merchantId: 'merchant_default',
    name: session.name,
    email: session.email,
  })
}

export function clearDemoSession() {
  clearAuthSession()
}
