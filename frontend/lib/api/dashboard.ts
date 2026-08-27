// frontend/lib/api/dashboard.ts
import { apiFetch, isApiMode } from './client'
import { DashboardBreakdown, DashboardSummary, DashboardTrends } from './types'
import { chartData as mockChartData, metrics as mockMetrics } from './payback'

export async function getDashboardSummary(): Promise<DashboardSummary> {
  if (!isApiMode()) {
    return {
      totalRevenueAtRisk: mockMetrics.atRisk,
      totalRecoveredRevenue: mockMetrics.recovered,
      overallRecoveryRate: mockMetrics.recoveryRate / 100,
      activeRecoveryCases: mockMetrics.activeCases,
      totalRecoveryCases: 150,
      successfulRecoveries: 104,
      escalatedCases: 12,
      stoppedCases: 8,
      averageRecoveryTimeHours: 2.4,
    }
  }

  const raw = await apiFetch<{
    total_revenue_at_risk: number
    total_recovered_revenue: number
    overall_recovery_rate: number
    active_recovery_cases: number
    total_recovery_cases: number
    successful_recoveries: number
    escalated_cases: number
    stopped_cases: number
    average_recovery_time_hours: number
  }>('/api/v1/dashboard/summary')

  return {
    totalRevenueAtRisk: raw.total_revenue_at_risk,
    totalRecoveredRevenue: raw.total_recovered_revenue,
    overallRecoveryRate: raw.overall_recovery_rate,
    activeRecoveryCases: raw.active_recovery_cases,
    totalRecoveryCases: raw.total_recovery_cases,
    successfulRecoveries: raw.successful_recoveries,
    escalatedCases: raw.escalated_cases,
    stoppedCases: raw.stopped_cases,
    averageRecoveryTimeHours: raw.average_recovery_time_hours,
  }
}

export async function getDashboardTrends(): Promise<DashboardTrends> {
  if (!isApiMode()) {
    return {
      period: '30d',
      trends: mockChartData.map((v, i) => ({
        date: `2024-08-${String(i + 1).padStart(2, '0')}`,
        atRiskAmount: 5000,
        recoveredAmount: Math.round(5000 * (v / 100)),
        recoveredCount: Math.round(v / 10),
        failedCount: Math.max(1, 10 - Math.round(v / 10)),
      })),
    }
  }

  const raw = await apiFetch<{
    period: string
    trends: Array<{
      date: string
      at_risk_amount: number
      recovered_amount: number
      recovered_count: number
      failed_count: number
    }>
  }>('/api/v1/dashboard/trends')

  return {
    period: raw.period,
    trends: raw.trends.map((t) => ({
      date: t.date,
      atRiskAmount: t.at_risk_amount,
      recoveredAmount: t.recovered_amount,
      recoveredCount: t.recovered_count,
      failedCount: t.failed_count,
    })),
  }
}

export async function getDashboardBreakdown(): Promise<DashboardBreakdown> {
  if (!isApiMode()) {
    return {
      byAction: [
        { action: 'smart_retry', count: 68, recoveredAmount: 95400, successRate: 0.72 },
        { action: 'whatsapp_payment_link', count: 42, recoveredAmount: 58800, successRate: 0.65 },
        { action: 'email_reminder', count: 36, recoveredAmount: 30000, successRate: 0.58 },
      ],
      byStatus: { in_review: 24, recovered: 104, failed: 22 },
      byPaymentMethod: { upi: 80, card: 50, netbanking: 20 },
    }
  }

  const raw = await apiFetch<{
    by_action: Array<{
      action: string
      count: number
      recovered_amount: number
      success_rate: number
    }>
    by_status: Record<string, number>
    by_payment_method: Record<string, number>
  }>('/api/v1/dashboard/breakdown')

  return {
    byAction: raw.by_action.map((a) => ({
      action: a.action,
      count: a.count,
      recoveredAmount: a.recovered_amount,
      successRate: a.success_rate,
    })),
    byStatus: raw.by_status,
    byPaymentMethod: raw.by_payment_method,
  }
}
