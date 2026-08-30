// frontend/lib/api/customers.ts
import { apiFetch, isApiMode } from './client'
import { ApiCustomer, CustomerDetail, RecoveryCase, Transaction } from './types'
import {
  customers as mockCustomers,
  getCustomer as getMockCustomer,
  getCustomerPayments as getMockPayments,
  getCustomerRecoveries as getMockRecoveries,
} from './payback'

export async function listCustomers(params?: { limit?: number; offset?: number }): Promise<ApiCustomer[]> {
  if (!isApiMode()) {
    const limit = params?.limit || 100
    const offset = params?.offset || 0
    const endIndex = Math.min(offset + limit, mockCustomers.length)
    return mockCustomers.slice(offset, endIndex).map((c) => ({
      id: c.id,
      name: c.name,
      email: c.email,
      phone: '+91 98765 43210',
      optedOut: false,
      createdAt: new Date().toISOString(),
    }))
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    external_id?: string
    name: string
    email?: string
    phone?: string
    opted_out: boolean
    total_paid_amount?: number
    open_recovery_cases?: number
    created_at: string
  }>>('/api/v1/customers', { params })

  return raw.map((c) => ({
    id: c.id,
    merchantId: c.merchant_id,
    externalId: c.external_id,
    name: c.name,
    email: c.email,
    phone: c.phone,
    optedOut: c.opted_out,
    totalPaidAmount: c.total_paid_amount ?? 0,
    openRecoveryCases: c.open_recovery_cases ?? 0,
    createdAt: c.created_at,
  }))
}

export async function getCustomerDetail(customerId: string): Promise<CustomerDetail> {
  if (!isApiMode()) {
    const c = getMockCustomer(customerId)
    const mockPayments = getMockPayments(customerId)
    const mockRecs = getMockRecoveries(customerId)

    return {
      customer: {
        id: c.id,
        name: c.name,
        email: c.email,
        phone: '+91 98765 43210',
        optedOut: false,
        createdAt: new Date().toISOString(),
      },
      metrics: {
        totalPayments: mockPayments.length || 3,
        successfulPayments: mockPayments.filter((p) => p.status === 'Succeeded').length || 2,
        failedPayments: mockPayments.filter((p) => p.status === 'Failed').length || 1,
        totalPaidAmount: c.lifetime,
        failedAmount: 2499,
        recoveryCasesCount: mockRecs.length || c.cases,
        successfulRecoveriesCount: mockRecs.filter((r) => r.status === 'Recovered').length || 1,
        recoveredRevenue: Math.round(c.lifetime * (c.recoveryRate / 100)),
        recoveryRate: c.recoveryRate / 100,
        historicalSuccessRate: 0.75,
        customerTenureDays: 180,
      },
      recentTransactions: mockPayments.map((p) => ({
        id: p.id,
        customerId: p.customerId,
        amount: p.amount,
        currency: 'INR',
        paymentMethod: p.method,
        status: p.status.toLowerCase(),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      })),
      recentRecoveries: mockRecs.map((r) => ({
        id: r.id,
        transactionId: `tx_${r.id.toLowerCase()}`,
        customerId: r.customerId,
        amountAtRisk: r.amount,
        reason: r.reason,
        status: r.status === 'Recovered' ? 'recovered' : r.status === 'In review' ? 'in_review' : 'failed',
        recoveryProbability: r.probability / 100,
        expectedValue: Math.round(r.amount * (r.probability / 100)),
        amountRecovered: r.status === 'Recovered' ? r.amount : 0,
        retryCount: 1,
        messageCount: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      })),
    }
  }

  const raw = await apiFetch<{
    customer: {
      id: string
      merchant_id?: string
      external_id?: string
      name: string
      email?: string
      phone?: string
      opted_out: boolean
      created_at: string
    }
    metrics: {
      total_payments: number
      successful_payments: number
      failed_payments: number
      total_paid_amount: number
      failed_amount: number
      recovery_cases_count: number
      successful_recoveries_count: number
      recovered_revenue: number
      recovery_rate: number
      historical_success_rate: number
      customer_tenure_days: number
    }
    recent_transactions: Array<{
      id: string
      merchant_id?: string
      customer_id: string
      amount: number
      currency: string
      payment_method: string
      status: string
      failure_reason?: string
      created_at: string
      updated_at: string
    }>
    recent_recoveries: Array<{
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
    }>
  }>(`/api/v1/customers/${customerId}`)

  return {
    customer: {
      id: raw.customer.id,
      merchantId: raw.customer.merchant_id,
      externalId: raw.customer.external_id,
      name: raw.customer.name,
      email: raw.customer.email,
      phone: raw.customer.phone,
      optedOut: raw.customer.opted_out,
      createdAt: raw.customer.created_at,
    },
    metrics: {
      totalPayments: raw.metrics.total_payments,
      successfulPayments: raw.metrics.successful_payments,
      failedPayments: raw.metrics.failed_payments,
      totalPaidAmount: raw.metrics.total_paid_amount,
      failedAmount: raw.metrics.failed_amount,
      recoveryCasesCount: raw.metrics.recovery_cases_count,
      successfulRecoveriesCount: raw.metrics.successful_recoveries_count,
      recoveredRevenue: raw.metrics.recovered_revenue,
      recoveryRate: raw.metrics.recovery_rate,
      historicalSuccessRate: raw.metrics.historical_success_rate,
      customerTenureDays: raw.metrics.customer_tenure_days,
    },
    recentTransactions: raw.recent_transactions.map((t) => ({
      id: t.id,
      merchantId: t.merchant_id,
      customerId: t.customer_id,
      amount: t.amount,
      currency: t.currency,
      paymentMethod: t.payment_method,
      status: t.status,
      failureReason: t.failure_reason,
      createdAt: t.created_at,
      updatedAt: t.updated_at,
    })),
    recentRecoveries: raw.recent_recoveries.map((r) => ({
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
    })),
  }
}

export async function getCustomerPayments(customerId: string): Promise<Transaction[]> {
  if (!isApiMode()) {
    const p = getMockPayments(customerId)
    return p.map((item) => ({
      id: item.id,
      customerId: item.customerId,
      amount: item.amount,
      currency: 'INR',
      paymentMethod: item.method,
      status: item.status.toLowerCase(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }))
  }

  const raw = await apiFetch<Array<{
    id: string
    merchant_id?: string
    customer_id: string
    amount: number
    currency: string
    payment_method: string
    status: string
    failure_reason?: string
    created_at: string
    updated_at: string
  }>>(`/api/v1/customers/${customerId}/payments`)

  return raw.map((t) => ({
    id: t.id,
    merchantId: t.merchant_id,
    customerId: t.customer_id,
    amount: t.amount,
    currency: t.currency,
    paymentMethod: t.payment_method,
    status: t.status,
    failureReason: t.failure_reason,
    createdAt: t.created_at,
    updatedAt: t.updated_at,
  }))
}

export async function getCustomerRecoveries(customerId: string): Promise<RecoveryCase[]> {
  if (!isApiMode()) {
    const r = getMockRecoveries(customerId)
    return r.map((item) => ({
      id: item.id,
      transactionId: `tx_${item.id.toLowerCase()}`,
      customerId: item.customerId,
      amountAtRisk: item.amount,
      reason: item.reason,
      status: item.status === 'Recovered' ? 'recovered' : item.status === 'In review' ? 'in_review' : 'failed',
      recoveryProbability: item.probability / 100,
      expectedValue: Math.round(item.amount * (item.probability / 100)),
      amountRecovered: item.status === 'Recovered' ? item.amount : 0,
      retryCount: 1,
      messageCount: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }))
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
  }>>(`/api/v1/customers/${customerId}/recoveries`)

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
