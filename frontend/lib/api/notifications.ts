// frontend/lib/api/notifications.ts
import { apiFetch, isApiMode } from './client'
import { ApiNotification, UnreadCount } from './types'
import {
  markAllNotificationsRead as mockMarkAllRead,
  markNotificationRead as mockMarkRead,
  notifications as mockNotifications,
} from './payback'

export async function listNotifications(params?: { limit?: number; unread_only?: boolean }): Promise<ApiNotification[]> {
  if (!isApiMode()) {
    return mockNotifications.map((n) => ({
      id: n.id,
      merchantId: 'merchant_default',
      notificationType: n.type,
      title: n.title,
      message: n.message,
      read: n.read,
      createdAt: new Date().toISOString(),
    }))
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id: string
    notification_type: string
    title: string
    message: string
    recovery_case_id?: string
    read: boolean
    created_at: string
  }>>('/api/v1/notifications', { params: params ? { limit: params.limit, unread_only: params.unread_only } : undefined })

  return raw.map((n) => ({
    id: n.id,
    merchantId: n.merchant_id,
    notificationType: n.notification_type,
    title: n.title,
    message: n.message,
    recoveryCaseId: n.recovery_case_id,
    read: n.read,
    createdAt: n.created_at,
  }))
}

export async function getUnreadCount(): Promise<UnreadCount> {
  if (!isApiMode()) {
    const unread = mockNotifications.filter((n) => !n.read).length
    return { unreadCount: unread }
  }

  const raw = await apiFetch<{ unread_count: number }>('/api/v1/notifications/unread-count')
  return { unreadCount: raw.unread_count }
}

export async function markNotificationRead(notificationId: string): Promise<ApiNotification> {
  if (!isApiMode()) {
    mockMarkRead(notificationId)
    const n = mockNotifications.find((x) => x.id === notificationId)
    return {
      id: notificationId,
      merchantId: 'merchant_default',
      notificationType: n?.type || 'payment_recovered',
      title: n?.title || 'Notification',
      message: n?.message || '',
      read: true,
      createdAt: new Date().toISOString(),
    }
  }

  const raw = await apiFetch<{
    id: string
    merchant_id: string
    notification_type: string
    title: string
    message: string
    recovery_case_id?: string
    read: boolean
    created_at: string
  }>(`/api/v1/notifications/${notificationId}/read`, {
    method: 'PATCH',
  })

  return {
    id: raw.id,
    merchantId: raw.merchant_id,
    notificationType: raw.notification_type,
    title: raw.title,
    message: raw.message,
    recoveryCaseId: raw.recovery_case_id,
    read: raw.read,
    createdAt: raw.created_at,
  }
}

export async function markAllNotificationsRead(): Promise<void> {
  if (!isApiMode()) {
    mockMarkAllRead()
    return
  }

  const list = await listNotifications({ unread_only: true })
  await Promise.all(list.map((n) => markNotificationRead(n.id)))
}
