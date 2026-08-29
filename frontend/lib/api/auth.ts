// frontend/lib/api/auth.ts
import { apiFetch, isApiMode } from './client'
import { AuthSession, MerchantProfile } from './types'
import { setAuthSession } from '@/lib/auth-session'

export async function login(email: string, password?: string): Promise<AuthSession> {
  if (!isApiMode()) {
    const mockSession: AuthSession = {
      accessToken: '',
      tokenType: 'bearer',
      merchantId: 'merchant_default',
      name: email.split('@')[0].replace(/[^a-zA-Z]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Demo Merchant',
      email,
    }
    setAuthSession(mockSession)
    return mockSession
  }

  const raw = await apiFetch<{
    access_token: string
    token_type: string
    merchant_id: string
    name: string
    email: string
  }>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password: password || 'demo-password' }),
  })

  const session: AuthSession = {
    accessToken: raw.access_token,
    tokenType: raw.token_type,
    merchantId: raw.merchant_id,
    name: raw.name,
    email: raw.email,
  }
  setAuthSession(session)
  return session
}


export async function register(name: string, email: string, phone?: string, password?: string): Promise<AuthSession> {
  if (!isApiMode()) {
    const mockSession: AuthSession = {
      accessToken: '',
      tokenType: 'bearer',
      merchantId: 'merchant_default',
      name,
      email,
    }
    setAuthSession(mockSession)
    return mockSession
  }

  const raw = await apiFetch<{
    access_token: string
    token_type: string
    merchant_id: string
    name: string
    email: string
  }>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name, email, phone, password: password || 'demo-password' }),
  })

  const session: AuthSession = {
    accessToken: raw.access_token,
    tokenType: raw.token_type,
    merchantId: raw.merchant_id,
    name: raw.name,
    email: raw.email,
  }
  setAuthSession(session)
  return session
}

export async function getMe(): Promise<MerchantProfile> {
  if (!isApiMode()) {
    return {
      id: 'merchant_default',
      name: 'Aditi Sharma',
      email: 'admin@payback.io',
      phone: '+91 98765 43210',
      timezone: 'Asia/Kolkata (IST)',
      createdAt: new Date().toISOString(),
    }
  }

  const raw = await apiFetch<{
    id: string
    name: string
    email: string
    phone?: string
    timezone: string
    created_at: string
  }>('/api/v1/auth/me')

  return {
    id: raw.id,
    name: raw.name,
    email: raw.email,
    phone: raw.phone,
    timezone: raw.timezone,
    createdAt: raw.created_at,
  }
}
