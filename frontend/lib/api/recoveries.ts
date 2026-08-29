// frontend/lib/api/recoveries.ts
import { apiFetch, isApiMode } from './client'
import { ActionRecord, AuditRecord, MessageDelivery, RecoveryCase, StartRecoveryPayload } from './types'
import { addRecovery as mockAddRecovery, recoveries as mockRecoveries } from './payback'

export async function listRecoveries(params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<RecoveryCase[]> {
  if (!isApiMode()) {
    let list = [...mockRecoveries].map((r) => ({
      id: r.id,
      transactionId: `tx_${r.id.toLowerCase()}`,
      customerId: r.customerId,
      amountAtRisk: r.amount,
      reason: r.reason,
      status: r.status === 'In review' ? 'in_review' : r.status === 'Recovered' ? 'recovered' : 'failed',
      recoverability: 'high',
      recoveryProbability: r.probability / 100,
      expectedValue: Math.round(r.amount * (r.probability / 100)),
      decisionReason: 'Customer has high recovery likelihood; low-friction sequence recommended.',
      selectedAction: 'smart_retry',
      amountRecovered: r.status === 'Recovered' ? r.amount : 0,
      retryCount: 1,
      messageCount: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }))

    if (params?.status) {
      list = list.filter((r) => r.status.toLowerCase() === params.status?.toLowerCase())
    }
    return list
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    transaction_id: string
    customer_id: string
    amount_at_risk: number
    reason: string
    status: string
    recoverability?: string
    recovery_probability: number
    expected_value: number
    decision_reason?: string
    decision?: string
    selected_action?: string
    stop_reason?: string
    escalate_reason?: string
    outcome?: string
    amount_recovered: number
    retry_count: number
    message_count: number
    created_at: string
    updated_at: string
  }>>('/api/v1/recoveries', { params })

  return raw.map((r) => ({
    id: r.id,
    merchantId: r.merchant_id,
    transactionId: r.transaction_id,
    customerId: r.customer_id,
    amountAtRisk: r.amount_at_risk,
    reason: r.reason,
    status: r.status,
    recoverability: r.recoverability,
    recoveryProbability: r.recovery_probability,
    expectedValue: r.expected_value,
    decisionReason: r.decision_reason,
    decision: r.decision,
    selectedAction: r.selected_action,
    stopReason: r.stop_reason,
    escalateReason: r.escalate_reason,
    outcome: r.outcome,
    amountRecovered: r.amount_recovered,
    retryCount: r.retry_count,
    messageCount: r.message_count,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  }))
}

export async function getRecovery(recoveryId: string): Promise<RecoveryCase> {
  if (!isApiMode()) {
    const list = await listRecoveries()
    return list.find((r) => r.id === recoveryId) || list[0]
  }

  const r = await apiFetch<{
    id: string
    merchant_id?: string
    transaction_id: string
    customer_id: string
    amount_at_risk: number
    reason: string
    status: string
    recoverability?: string
    recovery_probability: number
    expected_value: number
    decision_reason?: string
    decision?: string
    selected_action?: string
    stop_reason?: string
    escalate_reason?: string
    outcome?: string
    amount_recovered: number
    retry_count: number
    message_count: number
    created_at: string
    updated_at: string
  }>(`/api/v1/recoveries/${recoveryId}`)

  return {
    id: r.id,
    merchantId: r.merchant_id,
    transactionId: r.transaction_id,
    customerId: r.customer_id,
    amountAtRisk: r.amount_at_risk,
    reason: r.reason,
    status: r.status,
    recoverability: r.recoverability,
    recoveryProbability: r.recovery_probability,
    expectedValue: r.expected_value,
    decisionReason: r.decision_reason,
    decision: r.decision,
    selectedAction: r.selected_action,
    stopReason: r.stop_reason,
    escalateReason: r.escalate_reason,
    outcome: r.outcome,
    amountRecovered: r.amount_recovered,
    retryCount: r.retry_count,
    messageCount: r.message_count,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  }
}

export async function getRecoveryActions(recoveryId: string): Promise<ActionRecord[]> {
  if (!isApiMode()) {
    return [
      {
        id: `act_${recoveryId}_1`,
        recoveryCaseId: recoveryId,
        action: 'smart_retry',
        outcome: 'failed',
        detail: 'Initial smart retry timed out. Scheduling secondary channel.',
        executedAt: new Date().toISOString(),
      },
    ]
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    recovery_case_id: string
    action: string
    outcome?: string
    detail?: string
    external_ref?: string
    executed_at: string
  }>>(`/api/v1/recoveries/${recoveryId}/actions`)

  return raw.map((a) => ({
    id: a.id,
    merchantId: a.merchant_id,
    recoveryCaseId: a.recovery_case_id,
    action: a.action,
    outcome: a.outcome,
    detail: a.detail,
    externalRef: a.external_ref,
    executedAt: a.executed_at,
  }))
}

export async function getRecoveryTimeline(recoveryId: string, limit: number = 50): Promise<AuditRecord[]> {
  if (!isApiMode()) {
    return [
      {
        id: `aud_1`,
        recoveryCaseId: recoveryId,
        eventType: 'case_created',
        detail: 'Recovery case created automatically upon payment failure.',
        createdAt: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        id: `aud_2`,
        recoveryCaseId: recoveryId,
        eventType: 'ml_evaluated',
        detail: 'ML engine evaluated recovery probability at 78% (high likelihood).',
        createdAt: new Date(Date.now() - 3500000).toISOString(),
      },
      {
        id: `aud_3`,
        recoveryCaseId: recoveryId,
        eventType: 'action_dispatched',
        detail: 'Automated recovery sequence scheduled.',
        createdAt: new Date(Date.now() - 1800000).toISOString(),
      },
    ]
  }

  // Optimized: Add limit parameter for better performance
  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    recovery_case_id: string
    event_type: string
    detail: string
    created_at: string
  }>>(`/api/v1/recoveries/${recoveryId}/timeline?limit=${limit}`)

  return raw.map((t) => ({
    id: t.id,
    merchantId: t.merchant_id,
    recoveryCaseId: t.recovery_case_id,
    eventType: t.event_type,
    detail: t.detail,
    createdAt: t.created_at,
  }))
}

export async function getRecoveryMessages(recoveryId: string): Promise<MessageDelivery[]> {
  if (!isApiMode()) {
    return [
      {
        id: `msg_1`,
        recoveryCaseId: recoveryId,
        customerId: 'cus_default',
        channel: 'email',
        provider: 'mock',
        status: 'delivered',
        contentPreview: 'We noticed a payment issue. Click here to update your card.',
        createdAt: new Date().toISOString(),
      },
    ]
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    recovery_case_id: string
    customer_id: string
    channel: string
    provider: string
    provider_message_id?: string
    status: string
    content_preview?: string
    sent_at?: string
    delivered_at?: string
    failure_reason?: string
    created_at: string
  }>>(`/api/v1/recoveries/${recoveryId}/messages`)

  return raw.map((m) => ({
    id: m.id,
    merchantId: m.merchant_id,
    recoveryCaseId: m.recovery_case_id,
    customerId: m.customer_id,
    channel: m.channel,
    provider: m.provider,
    providerMessageId: m.provider_message_id,
    status: m.status,
    contentPreview: m.content_preview,
    sentAt: m.sent_at,
    deliveredAt: m.delivered_at,
    failureReason: m.failure_reason,
    createdAt: m.created_at,
  }))
}

export async function startRecovery(payload: StartRecoveryPayload): Promise<RecoveryCase> {
  if (!isApiMode()) {
    const created = mockAddRecovery({
      customerId: 'cus_maya',
      customer: 'Maya Shah',
      email: 'maya.shah@example.com',
      amount: 2499,
      status: 'In review',
      reason: 'Insufficient funds',
      payment: 'UPI ·•• 4821',
    })
    return {
      id: created.id,
      transactionId: 'tx_demo',
      customerId: 'cus_maya',
      amountAtRisk: created.amount,
      reason: created.reason,
      status: 'in_review',
      recoveryProbability: 0.78,
      expectedValue: 1949,
      amountRecovered: 0,
      retryCount: 0,
      messageCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
  }

  const r = await apiFetch<{
    id: string
    merchant_id?: string
    transaction_id: string
    customer_id: string
    amount_at_risk: number
    reason: string
    status: string
    recoverability?: string
    recovery_probability: number
    expected_value: number
    decision_reason?: string
    decision?: string
    selected_action?: string
    stop_reason?: string
    escalate_reason?: string
    outcome?: string
    amount_recovered: number
    retry_count: number
    message_count: number
    created_at: string
    updated_at: string
  }>('/api/v1/recoveries', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

  return {
    id: r.id,
    merchantId: r.merchant_id,
    transactionId: r.transaction_id,
    customerId: r.customer_id,
    amountAtRisk: r.amount_at_risk,
    reason: r.reason,
    status: r.status,
    recoverability: r.recoverability,
    recoveryProbability: r.recovery_probability,
    expectedValue: r.expected_value,
    decisionReason: r.decision_reason,
    decision: r.decision,
    selectedAction: r.selected_action,
    stopReason: r.stop_reason,
    escalateReason: r.escalate_reason,
    outcome: r.outcome,
    amountRecovered: r.amount_recovered,
    retryCount: r.retry_count,
    messageCount: r.message_count,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  }
}

export async function recordFailedPayment(payload: {
  customer_name: string
  customer_email: string
  transaction_amount: number
  payment_method: string
  failure_reason: string
}): Promise<RecoveryCase> {
  const methodMap: Record<string, string> = {
    'UPI': 'upi',
    'Visa Card': 'card',
    'Mastercard': 'card',
    'Netbanking': 'net_banking',
  }

  const raw = await apiFetch<{
    id: string
    merchant_id?: string
    transaction_id: string
    customer_id: string
    amount_at_risk: number
    reason: string
    status: string
    recoverability?: string
    recovery_probability: number
    expected_value: number
    decision_reason?: string
    decision?: string
    selected_action?: string
    stop_reason?: string
    escalate_reason?: string
    outcome?: string
    amount_recovered: number
    retry_count: number
    message_count: number
    created_at: string
    updated_at: string
  }>('/api/v1/events/payment', {
    method: 'POST',
    body: JSON.stringify({
      customer_external_id: `cus_${payload.customer_name.toLowerCase().replace(/\s+/g, '_')}`,
      customer_name: payload.customer_name,
      customer_email: payload.customer_email,
      transaction_amount: payload.transaction_amount,
      transaction_currency: 'INR',
      payment_method: methodMap[payload.payment_method] || 'upi',
      transaction_status: 'failed',
      failure_reason: payload.failure_reason,
    }),
  })

  return {
    id: raw.id,
    merchantId: raw.merchant_id,
    transactionId: raw.transaction_id,
    customerId: raw.customer_id,
    amountAtRisk: raw.amount_at_risk,
    reason: raw.reason,
    status: raw.status,
    recoverability: raw.recoverability,
    recoveryProbability: raw.recovery_probability,
    expectedValue: raw.expected_value,
    decisionReason: raw.decision_reason,
    decision: raw.decision,
    selectedAction: raw.selected_action,
    stopReason: raw.stop_reason,
    escalateReason: raw.escalate_reason,
    outcome: raw.outcome,
    amountRecovered: raw.amount_recovered,
    retryCount: raw.retry_count,
    messageCount: raw.message_count,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  }
}

