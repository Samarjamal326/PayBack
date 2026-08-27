// frontend/lib/api/settings.ts
import { apiFetch, isApiMode } from './client'
import { MerchantProfile, NotificationSettings } from './types'
import { updateWorkspaceSettings as mockUpdateSettings, workspaceSettings as mockSettings } from './payback'

export async function getProfile(): Promise<MerchantProfile> {
  if (!isApiMode()) {
    return {
      id: 'merchant_default',
      name: mockSettings.workspaceName,
      email: 'admin@payback.io',
      phone: '+91 98765 43210',
      timezone: mockSettings.timezone,
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
  }>('/api/v1/settings/profile')

  return {
    id: raw.id,
    name: raw.name,
    email: raw.email,
    phone: raw.phone,
    timezone: raw.timezone,
    createdAt: raw.created_at,
  }
}

export async function updateProfile(payload: { name?: string; phone?: string; timezone?: string }): Promise<MerchantProfile> {
  if (!isApiMode()) {
    mockUpdateSettings({
      workspaceName: payload.name || mockSettings.workspaceName,
      timezone: payload.timezone || mockSettings.timezone,
    })
    return getProfile()
  }

  const raw = await apiFetch<{
    id: string
    name: string
    email: string
    phone?: string
    timezone: string
    created_at: string
  }>('/api/v1/settings/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

  return {
    id: raw.id,
    name: raw.name,
    email: raw.email,
    phone: raw.phone,
    timezone: raw.timezone,
    createdAt: raw.created_at,
  }
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  if (!isApiMode()) {
    return {
      merchantId: 'merchant_default',
      notifyRecoveryCompleted: mockSettings.notifyRecoveryCompleted,
      notifyRecoveryEscalated: mockSettings.notifyRecoveryEscalated,
      notifyActionFailed: mockSettings.notifyActionFailed,
      notifyPaymentRecovered: mockSettings.notifyPaymentRecovered,
    }
  }

  const raw = await apiFetch<{
    merchant_id: string
    notify_recovery_completed: boolean
    notify_recovery_escalated: boolean
    notify_action_failed: boolean
    notify_payment_recovered: boolean
  }>('/api/v1/settings/notifications')

  return {
    merchantId: raw.merchant_id,
    notifyRecoveryCompleted: raw.notify_recovery_completed,
    notifyRecoveryEscalated: raw.notify_recovery_escalated,
    notifyActionFailed: raw.notify_action_failed,
    notifyPaymentRecovered: raw.notify_payment_recovered,
  }
}

export async function updateNotificationSettings(payload: Partial<{
  notifyRecoveryCompleted: boolean
  notifyRecoveryEscalated: boolean
  notifyActionFailed: boolean
  notifyPaymentRecovered: boolean
}>): Promise<NotificationSettings> {
  if (!isApiMode()) {
    mockUpdateSettings(payload)
    return getNotificationSettings()
  }

  const body: Record<string, unknown> = {}
  if (payload.notifyRecoveryCompleted !== undefined) body.notify_recovery_completed = payload.notifyRecoveryCompleted
  if (payload.notifyRecoveryEscalated !== undefined) body.notify_recovery_escalated = payload.notifyRecoveryEscalated
  if (payload.notifyActionFailed !== undefined) body.notify_action_failed = payload.notifyActionFailed
  if (payload.notifyPaymentRecovered !== undefined) body.notify_payment_recovered = payload.notifyPaymentRecovered

  const raw = await apiFetch<{
    merchant_id: string
    notify_recovery_completed: boolean
    notify_recovery_escalated: boolean
    notify_action_failed: boolean
    notify_payment_recovered: boolean
  }>('/api/v1/settings/notifications', {
    method: 'PUT',
    body: JSON.stringify(body),
  })

  return {
    merchantId: raw.merchant_id,
    notifyRecoveryCompleted: raw.notify_recovery_completed,
    notifyRecoveryEscalated: raw.notify_recovery_escalated,
    notifyActionFailed: raw.notify_action_failed,
    notifyPaymentRecovered: raw.notify_payment_recovered,
  }
}
