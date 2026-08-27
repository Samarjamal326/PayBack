// frontend/lib/api/policies.ts
import { apiFetch, isApiMode } from './client'
import { ApiPolicy, CreatePolicyPayload, UpdatePolicyPayload } from './types'
import { addPolicy as mockAddPolicy, policies as mockPolicies, updatePolicy as mockUpdatePolicy } from './payback'

export async function listPolicies(): Promise<ApiPolicy[]> {
  if (!isApiMode()) {
    return mockPolicies.map((p) => ({
      id: p.id,
      name: p.name,
      isActive: p.status === 'Active',
      maximumRetries: p.maxRetries,
      maximumMessages: p.maxMessages,
      recoveryWindowHours: p.recoveryWindowHours,
      highValueThreshold: p.highValueThreshold,
      humanApprovalRequired: p.humanApprovalRequired,
      actionCosts: { smart_retry: 0.1, email_reminder: 0.05, whatsapp_reminder: 0.25 },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }))
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    name: string
    is_active: boolean
    maximum_retries: number
    maximum_messages: number
    recovery_window_hours: number
    high_value_threshold: number
    human_approval_required: boolean
    action_costs: Record<string, number>
    created_at: string
    updated_at: string
  }>>('/api/v1/policies')

  return raw.map((p) => ({
    id: p.id,
    merchantId: p.merchant_id,
    name: p.name,
    isActive: p.is_active,
    maximumRetries: p.maximum_retries,
    maximumMessages: p.maximum_messages,
    recoveryWindowHours: p.recovery_window_hours,
    highValueThreshold: p.high_value_threshold,
    humanApprovalRequired: p.human_approval_required,
    actionCosts: p.action_costs,
    createdAt: p.created_at,
    updatedAt: p.updated_at,
  }))
}

export async function createPolicy(payload: CreatePolicyPayload): Promise<ApiPolicy> {
  if (!isApiMode()) {
    const created = mockAddPolicy({
      name: payload.name || 'New Policy',
      description: 'Automated recovery sequence policy',
      status: payload.isActive !== false ? 'Active' : 'Draft',
      maxRetries: payload.maximumRetries ?? 3,
      maxMessages: payload.maximumMessages ?? 2,
      recoveryWindowHours: payload.recoveryWindowHours ?? 72,
      highValueThreshold: payload.highValueThreshold ?? 10000,
      humanApprovalRequired: !!payload.humanApprovalRequired,
    })
    return {
      id: created.id,
      name: created.name,
      isActive: created.status === 'Active',
      maximumRetries: created.maxRetries,
      maximumMessages: created.maxMessages,
      recoveryWindowHours: created.recoveryWindowHours,
      highValueThreshold: created.highValueThreshold,
      humanApprovalRequired: created.humanApprovalRequired,
      actionCosts: { smart_retry: 0.1, email_reminder: 0.05, whatsapp_reminder: 0.25 },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
  }

  const p = await apiFetch<{
    id: string
    merchant_id?: string
    name: string
    is_active: boolean
    maximum_retries: number
    maximum_messages: number
    recovery_window_hours: number
    high_value_threshold: number
    human_approval_required: boolean
    action_costs: Record<string, number>
    created_at: string
    updated_at: string
  }>('/api/v1/policies', {
    method: 'POST',
    body: JSON.stringify({
      name: payload.name ?? 'New Policy',
      is_active: payload.isActive ?? true,
      maximum_retries: payload.maximumRetries ?? 3,
      maximum_messages: payload.maximumMessages ?? 3,
      recovery_window_hours: payload.recoveryWindowHours ?? 72,
      high_value_threshold: payload.highValueThreshold ?? 10000,
      human_approval_required: payload.humanApprovalRequired ?? false,
      action_costs: payload.actionCosts,
    }),
  })

  return {
    id: p.id,
    merchantId: p.merchant_id,
    name: p.name,
    isActive: p.is_active,
    maximumRetries: p.maximum_retries,
    maximumMessages: p.maximum_messages,
    recoveryWindowHours: p.recovery_window_hours,
    highValueThreshold: p.high_value_threshold,
    humanApprovalRequired: p.human_approval_required,
    actionCosts: p.action_costs,
    createdAt: p.created_at,
    updatedAt: p.updated_at,
  }
}

export async function updatePolicy(policyId: string, payload: UpdatePolicyPayload): Promise<ApiPolicy> {
  if (!isApiMode()) {
    const updated = mockUpdatePolicy(policyId, {
      name: payload.name,
      status: payload.isActive === undefined ? undefined : payload.isActive ? 'Active' : 'Draft',
      maxRetries: payload.maximumRetries,
      maxMessages: payload.maximumMessages,
      recoveryWindowHours: payload.recoveryWindowHours,
      highValueThreshold: payload.highValueThreshold,
      humanApprovalRequired: payload.humanApprovalRequired,
    })
    return {
      id: policyId,
      name: updated?.name || 'Updated Policy',
      isActive: updated?.status === 'Active',
      maximumRetries: updated?.maxRetries ?? 3,
      maximumMessages: updated?.maxMessages ?? 2,
      recoveryWindowHours: updated?.recoveryWindowHours ?? 72,
      highValueThreshold: updated?.highValueThreshold ?? 10000,
      humanApprovalRequired: !!updated?.humanApprovalRequired,
      actionCosts: { smart_retry: 0.1, email_reminder: 0.05, whatsapp_reminder: 0.25 },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
  }

  const body: Record<string, unknown> = {}
  if (payload.name !== undefined) body.name = payload.name
  if (payload.isActive !== undefined) body.is_active = payload.isActive
  if (payload.maximumRetries !== undefined) body.maximum_retries = payload.maximumRetries
  if (payload.maximumMessages !== undefined) body.maximum_messages = payload.maximumMessages
  if (payload.recoveryWindowHours !== undefined) body.recovery_window_hours = payload.recoveryWindowHours
  if (payload.highValueThreshold !== undefined) body.high_value_threshold = payload.highValueThreshold
  if (payload.humanApprovalRequired !== undefined) body.human_approval_required = payload.humanApprovalRequired
  if (payload.actionCosts !== undefined) body.action_costs = payload.actionCosts

  const p = await apiFetch<{
    id: string
    merchant_id?: string
    name: string
    is_active: boolean
    maximum_retries: number
    maximum_messages: number
    recovery_window_hours: number
    high_value_threshold: number
    human_approval_required: boolean
    action_costs: Record<string, number>
    created_at: string
    updated_at: string
  }>(`/api/v1/policies/${policyId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })

  return {
    id: p.id,
    merchantId: p.merchant_id,
    name: p.name,
    isActive: p.is_active,
    maximumRetries: p.maximum_retries,
    maximumMessages: p.maximum_messages,
    recoveryWindowHours: p.recovery_window_hours,
    highValueThreshold: p.high_value_threshold,
    humanApprovalRequired: p.human_approval_required,
    actionCosts: p.action_costs,
    createdAt: p.created_at,
    updatedAt: p.updated_at,
  }
}
