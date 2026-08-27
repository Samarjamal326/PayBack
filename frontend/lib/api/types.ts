// frontend/lib/api/types.ts
// Canonical frontend types derived from backend schemas.py
// Service layer normalises snake_case backend → camelCase frontend here.

export type AuthSession = {
  accessToken: string
  tokenType: string
  merchantId: string
  name: string
  email: string
}

export type MerchantProfile = {
  id: string
  name: string
  email: string
  phone?: string
  timezone: string
  createdAt: string
}

export type NotificationSettings = {
  merchantId: string
  notifyRecoveryCompleted: boolean
  notifyRecoveryEscalated: boolean
  notifyActionFailed: boolean
  notifyPaymentRecovered: boolean
}

// Dashboard
export type DashboardSummary = {
  totalRevenueAtRisk: number
  totalRecoveredRevenue: number
  overallRecoveryRate: number
  activeRecoveryCases: number
  totalRecoveryCases: number
  successfulRecoveries: number
  escalatedCases: number
  stoppedCases: number
  averageRecoveryTimeHours: number
}

export type TrendDataPoint = {
  date: string
  atRiskAmount: number
  recoveredAmount: number
  recoveredCount: number
  failedCount: number
}

export type DashboardTrends = {
  period: string
  trends: TrendDataPoint[]
}

export type ActionBreakdownItem = {
  action: string
  count: number
  recoveredAmount: number
  successRate: number
}

export type DashboardBreakdown = {
  byAction: ActionBreakdownItem[]
  byStatus: Record<string, number>
  byPaymentMethod: Record<string, number>
}

// Customer
export type ApiCustomer = {
  id: string
  merchantId?: string
  externalId?: string
  name: string
  email?: string
  phone?: string
  optedOut: boolean
  createdAt: string
}

export type CustomerMetrics = {
  totalPayments: number
  successfulPayments: number
  failedPayments: number
  totalPaidAmount: number
  failedAmount: number
  recoveryCasesCount: number
  successfulRecoveriesCount: number
  recoveredRevenue: number
  recoveryRate: number
  historicalSuccessRate: number
  customerTenureDays: number
}

export type CustomerDetail = {
  customer: ApiCustomer
  metrics: CustomerMetrics
  recentTransactions: Transaction[]
  recentRecoveries: RecoveryCase[]
}

// Transactions
export type Transaction = {
  id: string
  merchantId?: string
  customerId: string
  amount: number
  currency: string
  paymentMethod: string
  status: string
  failureReason?: string
  createdAt: string
  updatedAt: string
}

// Recoveries
export type RecoveryCase = {
  id: string
  merchantId?: string
  transactionId: string
  customerId: string
  amountAtRisk: number
  reason: string
  status: string
  recoverability?: string
  recoveryProbability: number
  expectedValue: number
  decisionReason?: string
  decision?: string
  selectedAction?: string
  stopReason?: string
  escalateReason?: string
  outcome?: string
  amountRecovered: number
  retryCount: number
  messageCount: number
  createdAt: string
  updatedAt: string
}

export type ActionRecord = {
  id: string
  merchantId?: string
  recoveryCaseId: string
  action: string
  outcome?: string
  detail?: string
  externalRef?: string
  executedAt: string
}

export type AuditRecord = {
  id: string
  merchantId?: string
  recoveryCaseId: string
  eventType: string
  detail: string
  createdAt: string
}

export type MessageDelivery = {
  id: string
  merchantId?: string
  recoveryCaseId: string
  customerId: string
  channel: string
  provider: string
  providerMessageId?: string
  status: string
  contentPreview?: string
  sentAt?: string
  deliveredAt?: string
  failureReason?: string
  createdAt: string
}

// Policies
export type ApiPolicy = {
  id: string
  merchantId?: string
  name: string
  isActive: boolean
  maximumRetries: number
  maximumMessages: number
  recoveryWindowHours: number
  highValueThreshold: number
  humanApprovalRequired: boolean
  actionCosts: Record<string, number>
  createdAt: string
  updatedAt: string
}

export type CreatePolicyPayload = {
  name?: string
  isActive?: boolean
  maximumRetries?: number
  maximumMessages?: number
  recoveryWindowHours?: number
  highValueThreshold?: number
  humanApprovalRequired?: boolean
  actionCosts?: Record<string, number>
  is_active?: boolean
  maximum_retries?: number
  maximum_messages?: number
  recovery_window_hours?: number
  high_value_threshold?: number
  human_approval_required?: boolean
  action_costs?: Record<string, number>
}

export type UpdatePolicyPayload = Partial<CreatePolicyPayload>

// Notifications
export type ApiNotification = {
  id: string
  merchantId: string
  notificationType: string
  title: string
  message: string
  recoveryCaseId?: string
  read: boolean
  createdAt: string
}

export type UnreadCount = {
  unreadCount: number
}

// Start Recovery Request
export type StartRecoveryPayload = {
  case_id: string
  maximum_retries?: number
  maximum_messages?: number
  recovery_window_hours?: number
  high_value_threshold?: number
  human_approval_required?: boolean
}

// API Error
export type ApiError = {
  code?: string
  message: string
  requestId?: string
  details?: unknown
}
