'use client'

const SESSION_KEY = 'payback-demo-session'
export type DemoSession = { email: string; name: string }
export function getDemoSession(): DemoSession | null { if (typeof window === 'undefined') return null; const raw = window.localStorage.getItem(SESSION_KEY); return raw ? JSON.parse(raw) as DemoSession : null }
export function setDemoSession(session: DemoSession) { window.localStorage.setItem(SESSION_KEY, JSON.stringify(session)) }
export function clearDemoSession() { window.localStorage.removeItem(SESSION_KEY) }
export { SESSION_KEY }
