'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { FormEvent, useEffect, useState } from 'react'
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Check,
  ChevronRight,
  CreditCard,
  Download,
  LayoutDashboard,
  Menu,
  Moon,
  MoreHorizontal,
  PanelLeft,
  PanelLeftClose,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
  X,
} from 'lucide-react'
import {
  chartData,
  Customer,
  customers,
  formatINR,
  getCustomer,
  getCustomerPayments,
  getCustomerRecoveries,
  getCustomerTimeline,
  getRecovery,
  markAllNotificationsRead,
  markNotificationRead,
  metrics,
  Notification,
  notifications as initialNotifications,
  policies as initialPolicies,
  Policy,
  recoveries as initialRecoveries,
  Recovery,
  type RecoveryStatus,
  updatePolicy,
  updateWorkspaceSettings,
  workspaceSettings as initialSettings,
  WorkspaceSettings,
} from '@/lib/api/payback'
import { clearAuthSession, clearDemoSession, getAuthSession } from '@/lib/auth-session'
import * as authService from '@/lib/api/auth'
import * as dashboardService from '@/lib/api/dashboard'
import * as recoveriesService from '@/lib/api/recoveries'
import * as customersService from '@/lib/api/customers'
import * as paymentsService from '@/lib/api/payments'
import type { CreatePaymentWithCustomerRequest, CreatePaymentResponse } from '@/lib/api/payments'
import * as policiesService from '@/lib/api/policies'
import * as settingsService from '@/lib/api/settings'
import * as notifService from '@/lib/api/notifications'
import type {
  DashboardSummary,
  DashboardTrends,
  DashboardBreakdown,
  RecoveryCase,
  ApiCustomer,
  CustomerDetail as ApiCustomerDetail,
  ApiPolicy,
  MerchantProfile,
  NotificationSettings,
  ApiNotification,
  AuditRecord,
} from '@/lib/api/types'

const nav = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },

  { href: '/recoveries', label: 'Recoveries', icon: Activity },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/customers', label: 'Customers', icon: Users },
]
const secondary = [
  { href: '/policies', label: 'Policies', icon: ShieldCheck },
  { href: '/settings', label: 'Settings', icon: Settings },
]

function Logo() {
  return (
    <div className="brand">
      <span className="brand-mark">P</span>
      <span>PayBack</span>
    </div>
  )
}


export function formatFailureReason(reason?: string): string {
  if (!reason) return 'Payment not completed'
  const trimmed = reason.trim()

  const mapping: Record<string, string> = {
    'BAD_REQUEST_ERROR': 'Invalid payment details provided',
    'INSUFFICIENT_FUNDS': 'Payment declined due to insufficient funds',
    'PAYMENT_FAILED': 'Payment processing could not be completed by bank',
    'GATEWAY_ERROR': 'Bank payment gateway error, ready for smart retry',
    'AUTHENTICATION_FAILED': 'Customer authentication / OTP verification failed',
    'INVALID_CARD': 'Card details could not be verified by payment network',
    'CARD_EXPIRED': 'Card has expired, update payment method',
    'INVALID_CVV': 'Incorrect CVV security code entered',
    'TIMEOUT': 'Payment session timed out waiting for authorization',
    'CANCELLED': 'Payment attempt was cancelled by customer',
    'card_declined': 'Card declined by issuing bank',
    'insufficient_funds': 'Insufficient funds in customer account',
    'payment_timed_out': 'Payment request timed out',
    'bank_declined': 'Transaction declined by customer bank',
  }

  if (mapping[trimmed]) return mapping[trimmed]
  if (trimmed.startsWith('#') || /^[A-Za-z0-9_]{10,}$/.test(trimmed)) {
    return 'Payment declined by bank network'
  }
  return trimmed.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatRecoveryStatus(status: string): string {
  const statusMap: Record<string, string> = {
    'detected': 'Payment Failed',
    'analyzing': 'Analyzing',
    'eligibility_check': 'Eligibility Check',
    'decision': 'Decision Pending',
    'action_pending': 'Action Pending',
    'action_executed': 'Action Executed',
    'monitoring': 'Monitoring',
    'recovered': 'Recovered',
    'escalated': 'Escalated',
    'stopped': 'Stopped',
    'in_review': 'In Review',
  }
  return statusMap[status] || status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatAuditRecord(record: AuditRecord): { title: string; description: string } {
  const event = record.eventType
  const detail = record.detail || ''

  const eventTitleMap: Record<string, string> = {
    payment_failed: 'Payment Failed',
    recovery_case_created: 'Recovery Case Initialized',
    eligibility_checked: 'Eligibility Verified',
    action_selected: 'Recovery Action Selected',
    payment_link_created: 'Recovery Link Generated',
    decision_made: 'Strategy Determined',
    payment_succeeded: 'Payment Recovered',
    recovery_completed: 'Case Closed · Recovered',
    recovery_stopped: 'Recovery Concluded',
    recovery_escalated: 'Escalated for Team Review',
    message_sent: 'Customer Reminder Sent',
  }

  const title = eventTitleMap[event] || event.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  // Clean up detail to be user-friendly without raw JSON / hashes
  let description = detail
  if (event === 'payment_failed') {
    description = 'The transaction was declined by the customer’s payment provider.'
  } else if (event === 'recovery_case_created') {
    description = 'PayBack opened an automated recovery workflow for this transaction.'
  } else if (event === 'eligibility_checked') {
    description = 'Customer evaluated against frequency caps, opt-out rules, and merchant policy.'
  } else if (event === 'action_selected') {
    if (detail.includes('create_payment_link')) {
      description = 'Generated a secure Razorpay recovery checkout link.'
    } else if (detail.includes('retry_payment')) {
      description = 'Scheduled automated background payment retry with provider.'
    } else {
      description = 'Selected best-fit recovery action from ML decision engine.'
    }
  } else if (event === 'payment_link_created') {
    description = 'Secure payment link created and attached to recovery case.'
  } else if (event === 'decision_made') {
    description = 'ML model determined highest-conversion recovery pathway.'
  } else if (event === 'payment_succeeded' || event === 'recovery_completed') {
    description = 'Customer completed payment successfully. Funds captured.'
  }

  return { title, description }
}

function Status({ status }: { status: string }) {
  const normalized = status.toLowerCase().replace(/_/g, ' ').replace(/-/g, ' ')

  let badgeClass = 'status-neutral'
  let label = status

  // Recovery lifecycle states
  if (normalized === 'recovered' || normalized === 'success' || normalized === 'completed' || normalized === 'active') {
    badgeClass = 'status-good'
    label = normalized === 'recovered' ? 'Recovered' : normalized === 'success' ? 'Succeeded' : 'Active'
  } else if (
    normalized === 'in review' ||
    normalized === 'detected' ||
    normalized === 'analyzing' ||
    normalized === 'eligibility check' ||
    normalized === 'decision' ||
    normalized === 'decision pending' ||
    normalized === 'action pending' ||
    normalized === 'awaiting customer' ||
    normalized === 'recovering' ||
    normalized === 'monitoring'
  ) {
    badgeClass = 'status-warn'
    if (normalized === 'detected') label = 'Payment Failed'
    else if (normalized === 'in review') label = 'In Review'
    else if (normalized === 'analyzing') label = 'Analyzing'
    else if (normalized === 'eligibility check') label = 'Eligibility Check'
    else if (normalized === 'decision' || normalized === 'decision pending') label = 'Decision Pending'
    else if (normalized === 'action pending') label = 'Action Pending'
    else if (normalized === 'awaiting customer') label = 'Awaiting Customer'
    else if (normalized === 'monitoring') label = 'Monitoring'
    else label = 'In Review'
  } else if (normalized === 'failed' || normalized === 'stopped' || normalized === 'cancelled') {
    badgeClass = 'status-bad'
    label = normalized === 'failed' ? 'Failed' : normalized === 'stopped' ? 'Stopped' : 'Cancelled'
  } else if (normalized === 'escalated') {
    badgeClass = 'status-warn'
    label = 'Escalated'
  } else if (
    normalized === 'payment link created' ||
    normalized === 'action executed' ||
    normalized === 'email sent' ||
    normalized === 'processing'
  ) {
    badgeClass = 'status-info'
    if (normalized === 'payment link created') label = 'Link Created'
    else if (normalized === 'action executed') label = 'Action Executed'
    else if (normalized === 'email sent') label = 'Email Sent'
    else label = 'Processing'
  } else if (normalized === 'pending') {
    badgeClass = 'status-neutral'
    label = 'Pending'
  }

  return (
    <span className={`status ${badgeClass}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {label}
    </span>
  )
}

function Sidebar({
  collapsed,
  setCollapsed,
  mobile,
  onNavigate,
  user,
}: {
  collapsed: boolean
  setCollapsed: (v: boolean | ((prev: boolean) => boolean)) => void
  mobile: boolean
  onNavigate?: () => void
  user?: { name: string; email: string } | null
}) {
  const pathname = usePathname()
  const displayName = user?.name || 'Workspace Admin'
  const displayEmail = user?.email || 'admin@payback.io'
  const initials = displayName
    .split(' ')
    .map((w: string) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'WA'

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''} ${mobile ? 'sidebar-mobile-open' : ''}`}>
      <div className="sidebar-brand">
        <Logo />
        {!collapsed && !mobile && (
          <button
            className="icon-btn"
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
            onClick={() => setCollapsed(true)}
          >
            <PanelLeftClose className="size-4" />
          </button>
        )}
      </div>
      <div className="sidebar-nav">
        <p className="eyebrow">Workspace</p>
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={`nav-link ${pathname.startsWith(href) ? 'nav-active' : ''}`}
            title={collapsed ? label : undefined}
          >
            <Icon className="size-[18px] shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        ))}
        <p className="eyebrow manage-label">Manage</p>
        {secondary.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={`nav-link ${pathname === href ? 'nav-active' : ''}`}
            title={collapsed ? label : undefined}
          >
            <Icon className="size-[18px] shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        ))}
      </div>
      <div className="sidebar-bottom">
        <div className="profile">
          <div className="avatar">{initials}</div>
          {!collapsed && (
            <div>
              <b>{displayName}</b>
              <span>{displayEmail}</span>
            </div>
          )}
          {!collapsed && (
            <details className="profile-menu ml-auto">
              <summary className="icon-btn" aria-label="Open profile menu">
                <MoreHorizontal className="size-4" />
              </summary>
              <div className="profile-popover">
                <Link href="/settings">Workspace</Link>
                <Link href="/settings">Preferences</Link>
                <button
                  onClick={() => {
                    clearAuthSession()
                    window.location.href = '/sign-in'
                  }}
                >
                  Log out
                </button>

              </div>
            </details>
          )}
        </div>
      </div>
    </aside>
  )
}

function Header({
  onMenu,
  dark,
  setDark,
  collapsed,
  setCollapsed,
  notifs,
  onMarkRead,
  onMarkAllRead,
  onNewPayment,
}: {
  onMenu: () => void
  dark: boolean
  setDark: (v: boolean) => void
  collapsed: boolean
  setCollapsed: (v: boolean | ((prev: boolean) => boolean)) => void
  notifs: Notification[]
  onMarkRead: (id: string) => void
  onMarkAllRead: () => void
  onNewPayment: () => void
}) {
  const [showNotifs, setShowNotifs] = useState(false)
  const unreadCount = notifs.filter((n) => !n.read).length

  return (
    <header className="topbar">
      <div className="flex items-center gap-3">
        <button className="icon-btn mobile-menu" onClick={onMenu} aria-label="Open navigation">
          <Menu className="size-5" />
        </button>
        {collapsed && (
          <button
            className="icon-btn desktop-collapse"
            onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <PanelLeft className="size-4" />
          </button>
        )}
        <div className="search">
          <Search className="size-4 text-muted-foreground shrink-0" />
          <input aria-label="Search" placeholder="Search customers, transactions..." />
        </div>
      </div>
      <div className="top-actions">
        <button className="button-primary button-sm" onClick={onNewPayment}>
          <CreditCard className="size-4" />
          Create Payment
        </button>
        <button className="icon-btn" onClick={() => setDark(!dark)} aria-label="Toggle theme" title={dark ? 'Light mode' : 'Dark mode'}>
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
        <button
          className="icon-btn relative"
          onClick={() => setShowNotifs(!showNotifs)}
          aria-label="Notifications"
          title="Notifications"
        >
          <Bell className="size-4" />
          {unreadCount > 0 && <span className="notification-dot" />}
        </button>

        {showNotifs && (
          <div className="notif-popover">
            <div className="notif-header">
              <h3>Notifications ({unreadCount} unread)</h3>
              {unreadCount > 0 && (
                <button className="text-xs text-primary font-medium hover:underline" onClick={onMarkAllRead}>
                  Mark all as read
                </button>
              )}
            </div>
            {notifs.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No notifications</p>
            ) : (
              notifs.map((n) => (
                <div
                  key={n.id}
                  className={`notif-item ${!n.read ? 'unread' : ''}`}
                  onClick={() => onMarkRead(n.id)}
                >
                  <b>{n.title}</b>
                  <p>{n.message}</p>
                  <span>{n.time}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </header>
  )
}

function Metric({
  label,
  value,
  change,
  positive = true,
  note,
}: {
  label: string
  value: string
  change: string
  positive?: boolean
  note: string
}) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <p>{label}</p>
        <span className={`change ${positive ? 'change-up' : 'change-down'}`}>
          {positive ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
          {change}
        </span>
      </div>
      <p className="metric-value">{value}</p>
      <p className="metric-note">{note}</p>
    </div>
  )
}

function MiniChart({ trends }: { trends?: DashboardTrends | null }) {
  if (trends && trends.trends.length > 0) {
    const maxVal = Math.max(...trends.trends.map((t) => t.recoveredAmount), 1)
    const ySteps = [1, 0.75, 0.5, 0.25, 0]
    
    // Calculate how many dates to show based on total data points
    const totalDataPoints = trends.trends.length
    const maxLabelsToShow = 6  // Show at most 6 date labels
    const stepSize = Math.max(1, Math.floor(totalDataPoints / maxLabelsToShow))
    
    return (
      <div className="chart-wrap">
        <div className="chart-y">
          {ySteps.map((f) => (
            <span key={f}>{formatINR(Math.round(maxVal * f))}</span>
          ))}
        </div>
        <div className="chart-grid">
          {trends.trends.map((t, i) => (
            <div
              key={t.date || i}
              className="chart-bar"
              style={{ height: `${Math.max(8, (t.recoveredAmount / maxVal) * 100)}%` }}
              title={`${t.date}: ${formatINR(t.recoveredAmount)} recovered (${t.recoveredCount} cases)`}
            />
          ))}
        </div>
        <div className="chart-x">
          {trends.trends.map((t, i) => (
            // Only show date labels at regular intervals to avoid overcrowding
            i % stepSize === 0 || i === totalDataPoints - 1 ? (
              <span key={t.date || i}>{t.date.slice(5)}</span>
            ) : null
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="chart-wrap" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '140px', color: 'var(--muted-foreground)' }}>
      <div style={{ textAlign: 'center' }}>
        <p style={{ fontSize: '13px', fontWeight: 500 }}>No recovery activity recorded yet</p>
        <span style={{ fontSize: '11px', opacity: 0.7 }}>Trends will populate automatically as failed payments are recovered</span>
      </div>
    </div>
  )
}

function RecoveryTable({
  recoveriesList,
  compact = false,
}: {
  recoveriesList: Recovery[]
  compact?: boolean
}) {
  const list = compact ? recoveriesList.slice(0, 4) : recoveriesList

  async function handleExportCSV() {
    try {
      // Fetch full merchant recovery list for export to ensure full dataset
      const fullRecoveries = await recoveriesService.listRecoveries({ limit: 500 })
      const dataToExport = fullRecoveries.length > 0 ? fullRecoveries : recoveriesList

      const headers = [
        'Recovery Case ID',
        'Customer ID',
        'Customer Name',
        'Customer Email',
        'Transaction ID',
        'Amount at Risk (INR)',
        'Payment Status',
        'Recovery Status',
        'Current Stage',
        'Failure Reason',
        'Recovery Probability (%)',
        'Selected Action',
        'Decision Reason',
        'Escalation Status',
        'Escalation Reason',
        'Amount Recovered (INR)',
        'Outcome',
        'Retry Count',
        'Message Count',
        'Created At',
        'Updated At',
      ]

      const escapeCSV = (val: any) => {
        if (val === null || val === undefined) return '""'
        const str = String(val).replace(/"/g, '""')
        return `"${str}"`
      }

      const rows = dataToExport.map((r: any) => [
        escapeCSV(r.id),
        escapeCSV(r.customerId),
        escapeCSV(r.customerName || r.customer || 'Unknown'),
        escapeCSV(r.customerEmail || r.email || 'Unknown'),
        escapeCSV(r.transactionId || 'N/A'),
        r.amountAtRisk ?? r.amount ?? 0,
        escapeCSV(r.paymentStatus || 'Unknown'),
        escapeCSV(r.status),
        escapeCSV(formatRecoveryStatus(r.status)),
        escapeCSV(formatFailureReason(r.reason)),
        r.recoveryProbability ? Math.round(r.recoveryProbability * 100) : r.probability ?? 0,
        escapeCSV(r.selectedAction || r.nextAction || 'N/A'),
        escapeCSV(r.decisionReason || 'N/A'),
        escapeCSV(r.escalateReason ? 'Escalated' : 'Not Escalated'),
        escapeCSV(r.escalateReason || 'N/A'),
        r.amountRecovered ?? (r.status === 'Recovered' || r.status === 'recovered' ? r.amountAtRisk ?? r.amount ?? 0 : 0),
        escapeCSV(r.outcome || 'N/A'),
        r.retryCount ?? r.retry_count ?? 0,
        r.messageCount ?? r.message_count ?? 0,
        escapeCSV(r.createdAt || r.created || new Date().toISOString()),
        escapeCSV(r.updatedAt || r.updated || new Date().toISOString()),
      ])

      const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
      const encodedUri = encodeURI(csvContent)
      const link = document.createElement('a')
      link.setAttribute('href', encodedUri)
      link.setAttribute('download', `payback_recoveries_${new Date().toISOString().slice(0, 10)}.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (err) {
      console.error('Failed to export full CSV:', err)
      // Fallback to local list
      const headers = ['Case ID', 'Customer', 'Email', 'Amount (INR)', 'Status', 'Reason', 'Created']
      const rows = recoveriesList.map((r) => [
        `"${r.id}"`,
        `"${r.customer}"`,
        `"${r.email}"`,
        r.amount,
        `"${r.status}"`,
        `"${formatFailureReason(r.reason)}"`,
        `"${r.created}"`,
      ])
      const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
      const encodedUri = encodeURI(csvContent)
      const link = document.createElement('a')
      link.setAttribute('href', encodedUri)
      link.setAttribute('download', `payback_recoveries_${new Date().toISOString().slice(0, 10)}.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }

  return (
    <div className="table-card">
      <div className="table-heading">
        <div>
          <p className="section-kicker">{compact ? 'Latest activity' : 'Recovery queue'}</p>
          <h2>{compact ? 'Recent recoveries' : 'All recoveries'}</h2>
        </div>
        {compact ? (
          <Link href="/recoveries" className="text-sm font-medium text-primary flex items-center gap-1">
            View all <ChevronRight className="size-4" />
          </Link>
        ) : (
          <button className="button-secondary" onClick={handleExportCSV} title="Export full recovery dataset to CSV">
            <Download className="size-4" />
            Export CSV
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        {list.length === 0 ? (
          <p className="text-sm text-muted-foreground p-6 text-center">No recoveries found</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/recoveries/${r.id}`} className="customer-link">
                      <span className="avatar small">
                        {(r.customer || 'Customer').split(' ').map((x: string) => x[0]).join('').toUpperCase().slice(0, 2)}
                      </span>
                      <span>
                        <b>{r.customer}</b>
                        <small>{r.id.slice(0, 16)}</small>
                      </span>
                    </Link>
                  </td>
                  <td className="font-medium">{formatINR(r.amount)}</td>
                  <td>
                    <Status status={r.status} />
                  </td>
                  <td className="text-muted-foreground">{formatFailureReason(r.reason)}</td>
                  <td className="text-muted-foreground">{r.created}</td>
                  <td>
                    <Link href={`/recoveries/${r.id}`} className="icon-btn" aria-label="View case">
                      <ChevronRight className="size-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function PageIntro({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle: string
  action?: React.ReactNode
}) {
  return (
    <div className="page-intro">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  )
}

function NewRecoveryDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean
  onClose: () => void
  onCreate: (rec: Omit<Recovery, 'id' | 'created' | 'probability' | 'nextAction'>) => void
}) {
  if (!open) return null

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const customer = String(fd.get('customer') || '')
    const email = String(fd.get('email') || '')
    const amount = Number(fd.get('amount') || 0)
    const reason = String(fd.get('reason') || 'card_declined')
    const payment = String(fd.get('payment') || 'Card ·•• 4242')

    onCreate({
      customerId: `cus_${customer.toLowerCase().replace(/\s+/g, '_')}`,
      customer,
      email,
      amount,
      status: 'In review',
      reason,
      payment,
    })
    onClose()
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <h2>New Recovery Case (Testing)</h2>
            <p>⚠️ This is a testing tool for manually creating recovery cases. For real payments, use the "Create Payment" feature.</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close dialog">
            <X className="size-4" />
          </button>
        </div>
        <form className="dialog-form" onSubmit={handleSubmit}>
          <label>
            Customer Name
            <input name="customer" required placeholder="e.g. Rahul Sharma" />
          </label>
          <label>
            Customer Email
            <input name="email" required type="email" placeholder="rahul@example.com" />
          </label>
          <div className="row">
            <label>
              Amount (₹ INR)
              <input name="amount" required type="number" min="1" step="1" placeholder="2499" />
            </label>
            <label>
              Payment Method
              <select name="payment">
                <option value="UPI ·•• 4821">UPI</option>
                <option value="Visa ·•• 1092">Visa Card</option>
                <option value="Mastercard ·•• 7204">Mastercard</option>
                <option value="Netbanking (HDFC)">Netbanking</option>
              </select>
            </label>
          </div>
          <label>
            Failure Reason
            <select name="reason">
              <option value="Insufficient funds">Insufficient funds</option>
              <option value="Card expired">Card expired</option>
              <option value="Bank declined">Bank declined</option>
              <option value="Payment timed out">Payment timed out</option>
            </select>
          </label>
          <div className="dialog-actions">
            <button type="button" className="button-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="button-primary">
              Create Recovery (Test)
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function NewPaymentDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean
  onClose: () => void
  onCreate: (customerData: any) => Promise<void>
}) {
  const [customerName, setCustomerName] = useState('')
  const [customerEmail, setCustomerEmail] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [amount, setAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('card')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [paymentLink, setPaymentLink] = useState('')
  const [paymentCreated, setPaymentCreated] = useState(false)
  const [paymentStatus, setPaymentStatus] = useState('')
  const [transactionId, setTransactionId] = useState('')

  if (!open) return null

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    
    if (!customerName.trim()) {
      setError('Please enter customer name')
      return
    }
    
    if (!customerEmail.trim()) {
      setError('Please enter customer email')
      return
    }
    
    if (!customerPhone.trim()) {
      setError('Please enter customer phone')
      return
    }
    
    const amountValue = Number(amount)
    if (!amountValue || amountValue <= 0) {
      setError('Please enter a valid amount')
      return
    }

    setLoading(true)
    try {
      const result = await onCreate({
        customer_name: customerName,
        customer_email: customerEmail,
        customer_phone: customerPhone,
        amount: amountValue,
        currency: 'INR',
        payment_method: paymentMethod
      })
      
      setPaymentLink(result.payment_link_url || '')
      setTransactionId(result.transaction_id || '')
      setPaymentStatus('pending')
      setPaymentCreated(true)
      
      // Start polling for payment status
      pollPaymentStatus(result.transaction_id || '')
      
      // Reset form for next payment
      setCustomerName('')
      setCustomerEmail('')
      setCustomerPhone('')
      setAmount('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create payment')
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setPaymentCreated(false)
    setPaymentLink('')
    setTransactionId('')
    setPaymentStatus('')
    setCustomerName('')
    setCustomerEmail('')
    setCustomerPhone('')
    setAmount('')
    setError('')
  }

  async function pollPaymentStatus(txId: string) {
    if (!txId) return
    try {
      const transaction = await paymentsService.getTransaction(txId)
      if (transaction && transaction.status) {
        // Map backend status to display status
        const normalizedStatus = transaction.status.toLowerCase()
        const previousStatus = paymentStatus
        
        if (normalizedStatus === 'success' || normalizedStatus === 'captured') {
          setPaymentStatus('success')
        } else if (normalizedStatus === 'failed') {
          setPaymentStatus('failed')
        } else {
          setPaymentStatus(transaction.status)
        }
        
        // If status changed from pending to terminal state, refresh app data
        if (previousStatus === 'pending' && (normalizedStatus === 'success' || normalizedStatus === 'captured' || normalizedStatus === 'failed')) {
          // Refresh all data to show updated recovery status
          refreshAppData()
        }
        
        // If still pending, continue polling every 2 seconds
        if (normalizedStatus === 'pending') {
          setTimeout(() => pollPaymentStatus(txId), 2000)
        }
      }
    } catch (error) {
      console.error('Failed to poll payment status:', error)
    }
  }

  async function refreshAppData() {
    try {
      const [recs, custs] = await Promise.all([
        recoveriesService.listRecoveries(),
        customersService.listCustomers(),
      ])

      const customerMap = new Map<string, { name: string; email: string }>()
      custs.forEach((c) => {
        customerMap.set(c.id, { name: c.name, email: c.email || `${c.id}@example.com` })
      })
      setCustomersList(custs)

      if (recs.length > 0) {
        setRecoveriesList(
          recs.map((r) => {
            const custInfo = customerMap.get(r.customerId)
            const custName = custInfo?.name || (r.customerId.includes('-') ? 'Rahul Verma' : r.customerId.replace('cus_', '').replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()))
            const custEmail = custInfo?.email || 'customer@example.com'
            return {
              id: r.id,
              customerId: r.customerId,
              customer: custName,
              email: custEmail,
              amount: r.amountAtRisk,
              status: formatRecoveryStatus(r.status),
              reason: r.reason,
              created: 'Today, ' + new Date(r.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              payment: 'UPI ·•• 4821',
              probability: Math.round(r.recoveryProbability * 100),
              nextAction: r.selectedAction ? r.selectedAction.replace(/_/g, ' ') : 'Send reminder',
            }
          })
        )
      }
    } catch (err) {
      console.error('Failed to refresh app data:', err)
    }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <h2>{paymentCreated ? 'Payment Link Created' : 'Create Payment'}</h2>
            <p>{paymentCreated 
              ? 'Payment link created successfully. Use it to test the payment flow.'
              : 'Create a Razorpay Test Mode payment link for a new customer.'}
            </p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close dialog">
            <X className="size-4" />
          </button>
        </div>
        
        {paymentCreated ? (
          <div className="dialog-form">
            <div className="payment-link-display">
              <p className="text-sm font-medium mb-3">Payment Link Created Successfully!</p>

              {/* Payment Status Indicator */}
              <div className="mb-4 p-3 rounded-md" style={{
                background: paymentStatus === 'success' || paymentStatus === 'captured' || paymentStatus === 'completed'
                  ? 'rgba(34, 197, 94, 0.15)'
                  : paymentStatus === 'failed'
                    ? 'rgba(239, 68, 68, 0.15)'
                    : 'rgba(234, 179, 8, 0.15)',
                border: paymentStatus === 'success' || paymentStatus === 'captured' || paymentStatus === 'completed'
                  ? '1px solid rgba(34, 197, 94, 0.3)'
                  : paymentStatus === 'failed'
                    ? '1px solid rgba(239, 68, 68, 0.3)'
                    : '1px solid rgba(234, 179, 8, 0.3)'
              }}>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    paymentStatus === 'success' || paymentStatus === 'captured' || paymentStatus === 'completed'
                      ? 'bg-green-500'
                      : paymentStatus === 'failed'
                        ? 'bg-red-500'
                        : 'bg-yellow-500 animate-pulse'
                  }`}></div>
                  <span className="text-sm font-medium">
                    Status: {paymentStatus === 'success' || paymentStatus === 'captured' ? 'Successful' : paymentStatus === 'failed' ? 'Failed' : paymentStatus ? paymentStatus.charAt(0).toUpperCase() + paymentStatus.slice(1) : 'Pending'}
                  </span>
                </div>
              </div>

              <div className="payment-link-box">
                <input
                  value={paymentLink}
                  readOnly
                  className="payment-link-input"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: '6px',
                    background: 'var(--muted)',
                    color: 'var(--foreground)',
                    fontSize: '13px'
                  }}
                />
                <button
                  onClick={() => navigator.clipboard.writeText(paymentLink)}
                  className="button-secondary"
                  style={{ marginLeft: '8px' }}
                >
                  Copy Link
                </button>
                <button
                  onClick={() => window.open(paymentLink, '_blank')}
                  className="button-primary"
                  style={{ marginLeft: '8px' }}
                >
                  Open Link
                </button>
              </div>
              <p className="text-xs text-muted-foreground mt-3" style={{ lineHeight: '1.4' }}>
                <strong>Testing Instructions:</strong><br/>
                1. Click "Open Link" to make a test payment<br/>
                2. You can intentionally fail the payment to test the recovery process<br/>
                3. If payment succeeds, no recovery action will be taken<br/>
                4. If payment fails, the system will automatically start the recovery process
              </p>
            </div>
            <div className="dialog-actions">
              <button type="button" className="button-ghost" onClick={handleReset}>
                Create Another Payment
              </button>
              <button type="button" className="button-primary" onClick={onClose}>
                Done
              </button>
            </div>
          </div>
        ) : (
          <form className="dialog-form" onSubmit={handleSubmit}>
            {error && (
              <div className="alert alert-error" role="alert">
                {error}
              </div>
            )}
            <label>
              Customer Name
              <input 
                name="customerName" 
                required 
                placeholder="e.g. Rahul Sharma" 
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
              />
            </label>
            <label>
              Customer Email
              <input 
                name="customerEmail" 
                required 
                type="email" 
                placeholder="rahul@example.com"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
              />
            </label>
            <label>
              Customer Phone
              <input 
                name="customerPhone" 
                required 
                type="tel" 
                placeholder="9876543210"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
              />
            </label>
            <div className="row">
              <label>
                Amount (₹ INR)
                <input 
                  name="amount" 
                  required 
                  type="number" 
                  min="1" 
                  step="1" 
                  placeholder="2499"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </label>
              <label>
                Payment Method
                <select 
                  name="paymentMethod" 
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                >
                  <option value="card">Card</option>
                  <option value="upi">UPI</option>
                  <option value="net_banking">Netbanking</option>
                </select>
              </label>
            </div>
            <div className="dialog-actions">
              <button type="button" className="button-ghost" onClick={onClose} disabled={loading}>
                Cancel
              </button>
              <button type="submit" className="button-primary" disabled={loading}>
                {loading ? 'Creating...' : 'Create Payment Link'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function PolicyDialog({
  open,
  policy,
  onClose,
  onSave,
}: {
  open: boolean
  policy: Policy | null
  onClose: () => void
  onSave: (pol: Omit<Policy, 'id'>, id?: string) => void
}) {
  if (!open) return null

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const name = String(fd.get('name') || '')
    const description = String(fd.get('description') || '')
    const maxRetries = Number(fd.get('maxRetries') || 3)
    const maxMessages = Number(fd.get('maxMessages') || 2)
    const recoveryWindowHours = Number(fd.get('recoveryWindowHours') || 72)
    const highValueThreshold = Number(fd.get('highValueThreshold') || 10000)
    const status = String(fd.get('status') || 'Active') as 'Active' | 'Draft'
    const humanApprovalRequired = fd.get('humanApprovalRequired') === 'on'

    onSave(
      {
        name,
        description,
        status,
        maxRetries,
        maxMessages,
        recoveryWindowHours,
        highValueThreshold,
        humanApprovalRequired,
      },
      policy?.id
    )
    onClose()
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <h2>{policy ? 'Edit Policy' : 'Create Policy'}</h2>
            <p>Configure automated recovery limits, channels, and escalation thresholds.</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close dialog">
            <X className="size-4" />
          </button>
        </div>
        <form className="dialog-form" onSubmit={handleSubmit}>
          <label>
            Policy Name
            <input name="name" defaultValue={policy?.name || ''} required placeholder="e.g. Standard Retry Policy" />
          </label>
          <label>
            Description
            <textarea
              name="description"
              rows={2}
              defaultValue={policy?.description || ''}
              required
              placeholder="Explain what this policy controls..."
            />
          </label>
          <div className="row">
            <label>
              Max Retries
              <input name="maxRetries" type="number" min="1" max="10" defaultValue={policy?.maxRetries ?? 3} required />
            </label>
            <label>
              Max Messages
              <input name="maxMessages" type="number" min="1" max="10" defaultValue={policy?.maxMessages ?? 2} required />
            </label>
          </div>
          <div className="row">
            <label>
              Recovery Window (Hours)
              <input name="recoveryWindowHours" type="number" min="1" defaultValue={policy?.recoveryWindowHours ?? 72} required />
            </label>
            <label>
              High Value Threshold (₹)
              <input name="highValueThreshold" type="number" min="500" step="500" defaultValue={policy?.highValueThreshold ?? 10000} required />
            </label>
          </div>
          <div className="row">
            <label>
              Status
              <select name="status" defaultValue={policy?.status || 'Active'}>
                <option value="Active">Active</option>
                <option value="Draft">Draft</option>
              </select>
            </label>
            <label className="check mt-5">
              <input name="humanApprovalRequired" type="checkbox" defaultChecked={policy?.humanApprovalRequired ?? false} />
              Human approval required
            </label>
          </div>
          <div className="dialog-actions">
            <button type="button" className="button-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="button-primary">
              {policy ? 'Save Changes' : 'Create Policy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function SettingsDialog({
  open,
  kind,
  settings,
  onClose,
  onSave,
}: {
  open: boolean
  kind: 'workspace' | 'notifications' | 'account' | null
  settings: WorkspaceSettings
  onClose: () => void
  onSave: (updated: Partial<WorkspaceSettings>) => void
}) {
  if (!open || !kind) return null

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    if (kind === 'workspace') {
      onSave({
        workspaceName: String(fd.get('workspaceName') || ''),
        timezone: String(fd.get('timezone') || ''),
      })
    } else if (kind === 'notifications') {
      onSave({
        notifyRecoveryCompleted: fd.get('notifyRecoveryCompleted') === 'on',
        notifyRecoveryEscalated: fd.get('notifyRecoveryEscalated') === 'on',
        notifyActionFailed: fd.get('notifyActionFailed') === 'on',
        notifyPaymentRecovered: fd.get('notifyPaymentRecovered') === 'on',
      })
    }
    onClose()
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <h2>
              {kind === 'workspace'
                ? 'Workspace Preferences'
                : kind === 'notifications'
                ? 'Notification Preferences'
                : 'Account Details'}
            </h2>
            <p>
              {kind === 'workspace'
                ? 'Update your organization identifier and operating timezone.'
                : kind === 'notifications'
                ? 'Choose which automated recovery events alert your team.'
                : 'Current authenticated merchant profile.'}
            </p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close dialog">
            <X className="size-4" />
          </button>
        </div>

        {kind === 'account' ? (
          <div className="dialog-form">
            <div className="customer-profile">
              <div className="avatar large">AS</div>
              <div>
                <h3>Aditi Sharma</h3>
                <p>admin@payback.io · Workspace Admin</p>
              </div>
            </div>
            <div className="side-row">
              <span>Merchant ID</span>
              <b>merchant_default</b>
            </div>
            <div className="side-row">
              <span>Environment</span>
              <b>Production Ready (Phase 4)</b>
            </div>
            <div className="dialog-actions">
              <button
                type="button"
                className="button-ghost"
                onClick={() => {
                  clearDemoSession()
                  window.location.href = '/sign-in'
                }}
              >
                Log out
              </button>
              <button type="button" className="button-primary" onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        ) : (
          <form className="dialog-form" onSubmit={handleSubmit}>
            {kind === 'workspace' && (
              <>
                <label>
                  Workspace Name
                  <input name="workspaceName" defaultValue={settings.workspaceName} required />
                </label>
                <label>
                  Timezone
                  <select name="timezone" defaultValue={settings.timezone}>
                    <option value="Asia/Kolkata (IST)">Asia/Kolkata (IST)</option>
                    <option value="America/New_York (EST)">America/New_York (EST)</option>
                    <option value="Europe/London (GMT)">Europe/London (GMT)</option>
                    <option value="Asia/Singapore (SGT)">Asia/Singapore (SGT)</option>
                  </select>
                </label>
              </>
            )}
            {kind === 'notifications' && (
              <>
                <label className="check">
                  <input name="notifyPaymentRecovered" type="checkbox" defaultChecked={settings.notifyPaymentRecovered} />
                  Payment Recovered Alerts
                </label>
                <label className="check">
                  <input name="notifyRecoveryEscalated" type="checkbox" defaultChecked={settings.notifyRecoveryEscalated} />
                  High-Value Escalation Alerts
                </label>
                <label className="check">
                  <input name="notifyRecoveryCompleted" type="checkbox" defaultChecked={settings.notifyRecoveryCompleted} />
                  Recovery Completed Summaries
                </label>
                <label className="check">
                  <input name="notifyActionFailed" type="checkbox" defaultChecked={settings.notifyActionFailed} />
                  Action Failure / Retry Notifications
                </label>
              </>
            )}
            <div className="dialog-actions">
              <button type="button" className="button-ghost" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="button-primary">
                Save Preferences
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function Dashboard({ user }: { user?: { name: string; email: string } | null }) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [trends, setTrends] = useState<DashboardTrends | null>(null)
  const [breakdown, setBreakdown] = useState<DashboardBreakdown | null>(null)
  const [recentRecs, setRecentRecs] = useState<Recovery[]>([])
  const [loading, setLoading] = useState(true)

  const firstName = user?.name ? user.name.split(' ')[0] : 'Merchant'

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        // Optimized: Parallelize all independent dashboard API calls
        const [sum, tr, bdown, recs, custs] = await Promise.all([
          dashboardService.getDashboardSummary(),
          dashboardService.getDashboardTrends(),
          dashboardService.getDashboardBreakdown(),
          recoveriesService.listRecoveries({ limit: 5 }),
          customersService.listCustomers({ limit: 20 }), // Reduced from default 100 to 20
        ])
        if (!mounted) return
        setSummary(sum)
        setTrends(tr)
        setBreakdown(bdown)

        const customerMap = new Map<string, { name: string; email: string }>()
        custs.forEach((c) => {
          customerMap.set(c.id, { name: c.name, email: c.email || `${c.id}@example.com` })
        })

        if (recs.length > 0) {
          setRecentRecs(
            recs.map((r) => {
              const custInfo = customerMap.get(r.customerId)
              return {
                id: r.id,
                customerId: r.customerId,
                customer: custInfo?.name || r.customerId.replace('cus_', '').replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) || 'Customer',
                email: custInfo?.email || `${r.customerId}@example.com`,
                amount: r.amountAtRisk,
                status: formatRecoveryStatus(r.status),
                reason: r.reason,
                created: 'Today, ' + new Date(r.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                payment: 'UPI ·•• 4821',
                probability: Math.round(r.recoveryProbability * 100),
                nextAction: r.selectedAction ? r.selectedAction.replace(/_/g, ' ') : 'Send reminder',
              }
            })
          )
        }
      } catch (err) {
        console.error('Failed to load dashboard data:', err)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const recoveredVal = summary ? summary.totalRecoveredRevenue : 0
  const recoveryRateVal = summary ? (summary.overallRecoveryRate * 100).toFixed(1) : '0.0'
  const atRiskVal = summary ? summary.totalRevenueAtRisk : 0
  const activeCasesVal = summary ? summary.activeRecoveryCases : 0

  return (
    <>
      <PageIntro
        title="Overview"
        subtitle={`Welcome back, ${firstName}. Here is your recovery performance.`}
      />
      <div className="metric-grid">
        <Metric label="Recovered this month" value={formatINR(recoveredVal)} change="Live" note="Real-time recovery total" />
        <Metric label="Recovery rate" value={`${recoveryRateVal}%`} change="Live" note="Calculated from real transactions" />
        <Metric label="At risk" value={formatINR(atRiskVal)} change="Live" positive={false} note="Across active cases" />
        <Metric label="Active cases" value={activeCasesVal.toString()} change="Live" note="Real-time queue" />
      </div>
      <div className="dashboard-grid">
        <div className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Performance</p>
              <h2>Recovered revenue</h2>
            </div>
          </div>
          <div className="legend">
            <span>
              <i className="dot bg-primary" />
              Recovered
            </span>
            <span>
              <i className="dot bg-muted-foreground" />
              At risk
            </span>
          </div>
          <MiniChart trends={trends} />
        </div>
        <div className="panel breakdown">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Breakdown</p>
              <h2>Recovery by action</h2>
            </div>
            <MoreHorizontal className="size-5 text-muted-foreground" />
          </div>
          <div className="donut">
            <div>
              <strong>{recoveryRateVal}%</strong>
              <span>recovered</span>
            </div>
          </div>
          <div className="channel-list">
            {breakdown?.byAction?.length ? (
              breakdown.byAction.map((a, i) => (
                <div key={a.action}>
                  <span>
                    <i className={`dot ${i === 0 ? 'bg-primary' : i === 1 ? 'bg-success' : 'bg-warning'}`} />
                    {a.action.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                  </span>
                  <b>{a.count} cases ({formatINR(a.recoveredAmount)})</b>
                </div>
              ))
            ) : (
              <>
                <div>
                  <span>
                    <i className="dot bg-primary" />
                    Payment Link
                  </span>
                  <b>—</b>
                </div>
                <div>
                  <span>
                    <i className="dot bg-success" />
                    Smart Retry
                  </span>
                  <b>—</b>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      <RecoveryTable recoveriesList={recentRecs} compact />
      
      {/* Recent Payment Links Section */}
      <div className="panel" style={{ marginTop: '24px' }}>
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Testing</p>
            <h2>Payment Link Testing</h2>
          </div>
        </div>
        <div style={{ padding: '16px' }}>
          <p className="text-sm text-muted-foreground mb-4">
            Use the "Create Payment" button above to generate test payment links. Click the generated links to make test payments and observe the recovery process.
          </p>
          <div style={{ 
            padding: '12px', 
            background: 'var(--muted)', 
            borderRadius: '8px',
            border: '1px solid var(--border)'
          }}>
            <p className="text-sm font-medium mb-2">Testing Workflow:</p>
            <ol className="text-sm text-muted-foreground" style={{ paddingLeft: '20px', margin: 0 }}>
              <li style={{ marginBottom: '8px' }}>Click "Create Payment" and enter customer details</li>
              <li style={{ marginBottom: '8px' }}>Copy or open the generated payment link</li>
              <li style={{ marginBottom: '8px' }}>Make a test payment (succeed or fail intentionally)</li>
              <li style={{ marginBottom: '8px' }}>Watch the recovery process in the "Recoveries" tab</li>
              <li>Success: No recovery action • Failure: Automatic recovery triggers</li>
            </ol>
          </div>
        </div>
      </div>
    </>
  )
}


function Recoveries({
  recoveriesList,
  onNewRecovery,
}: {
  recoveriesList: Recovery[]
  onNewRecovery: () => void
}) {
  const [filter, setFilter] = useState<string>('All')
  
  // Get unique statuses from the actual data
  const uniqueStatuses = Array.from(new Set(recoveriesList.map(r => r.status)))
  
  const filtered = filter === 'All' ? recoveriesList : recoveriesList.filter((r) => r.status === filter)

  return (
    <>
      <PageIntro
        title="Recoveries"
        subtitle="Track and manage every payment recovery in one place."
        action={
          <button className="button-primary" onClick={onNewRecovery}>
            <Plus className="size-4" />
            New recovery
          </button>
        }
      />
      <div className="filter-row">
        <button className={`filter ${filter === 'All' ? 'active' : ''}`} onClick={() => setFilter('All')}>
          All <span>{recoveriesList.length}</span>
        </button>
        {uniqueStatuses.map(status => (
          <button 
            key={status} 
            className={`filter ${filter === status ? 'active' : ''}`} 
            onClick={() => setFilter(status)}
          >
            {status} <span>{recoveriesList.filter((r) => r.status === status).length}</span>
          </button>
        ))}
      </div>
      <RecoveryTable recoveriesList={filtered} />
    </>
  )
}

function Detail({ id }: { id: string }) {
  const [caseData, setCaseData] = useState<RecoveryCase | null>(null)
  const [timeline, setTimeline] = useState<AuditRecord[]>([])
  const [customer, setCustomer] = useState<ApiCustomer | null>(null)
  const [customerMetrics, setCustomerMetrics] = useState<{ totalPaidAmount: number; recoveryCasesCount: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(null)
    async function load() {
      try {
        // Optimized: Parallelize recovery data and customer detail fetching
        const [c, tl] = await Promise.all([
          recoveriesService.getRecovery(id),
          recoveriesService.getRecoveryTimeline(id, 20),
        ])
        if (!mounted) return
        setCaseData(c)
        setTimeline(tl)

        if (c.customerId) {
          try {
            const custDetail = await customersService.getCustomerDetail(c.customerId)
            if (mounted && custDetail) {
              setCustomer(custDetail.customer)
              setCustomerMetrics({
                totalPaidAmount: custDetail.metrics.totalPaidAmount,
                recoveryCasesCount: custDetail.metrics.recoveryCasesCount,
              })
            }
          } catch {
            // non-fatal
          }
        }
      } catch (err) {
        if (!mounted) return
        console.error('Failed to load recovery detail:', err)
        setError(err instanceof Error ? err.message : 'Recovery case not found')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [id])

  if (loading) {
    return (
      <>
        <Link href="/recoveries" className="back-link">
          ← Back to recoveries
        </Link>
        <PageIntro title="Loading recovery case..." subtitle="Fetching recovery workflow and timeline data..." />
        <div className="panel" style={{ padding: '32px', textAlign: 'center' }}>
          <p className="text-muted-foreground">Loading case details...</p>
        </div>
      </>
    )
  }

  if (error || !caseData) {
    return (
      <>
        <Link href="/recoveries" className="back-link">
          ← Back to recoveries
        </Link>
        <div className="panel" style={{ padding: '32px', textAlign: 'center' }}>
          <h2>Recovery Case Not Found</h2>
          <p className="text-muted-foreground mt-2 mb-4">
            {error || `No recovery case was found with ID '${id}' in your workspace.`}
          </p>
          <Link href="/recoveries" className="button-primary">
            Return to Recoveries
          </Link>
        </div>
      </>
    )
  }

  const prob = Math.round(caseData.recoveryProbability * 100)
  const amount = caseData.amountAtRisk
  const reason = formatFailureReason(caseData.reason)
  const statusStr: RecoveryStatus = formatRecoveryStatus(caseData.status)

  const radius = 42
  const stroke = 6
  const normalizedRadius = radius - stroke * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - (prob / 100) * circumference

  const customerDisplayName = customer?.name || 'Customer'
  const customerEmailDisplay = customer?.email || (caseData.customerId ? `${caseData.customerId}@example.com` : 'N/A')

  return (
    <>
      <Link href="/recoveries" className="back-link">
        ← Back to recoveries
      </Link>
      <PageIntro
        title={customerDisplayName}
        subtitle={`${id} · Created ${new Date(caseData.createdAt).toLocaleString()}`}
        action={<Status status={statusStr} />}
      />
      <div className="detail-grid">
        <div className="detail-main">
          <div className="hero-amount">
            <div>
              <p className="section-kicker">Amount to recover</p>
              <div className="amount">{formatINR(amount)}</div>
              <p className="text-sm text-muted-foreground">
                Action: {caseData.selectedAction ? caseData.selectedAction.replace(/_/g, ' ') : 'Analyzing'}
              </p>
            </div>
            <div className="score">
              <svg height="104" width="104">
                <circle
                  stroke="var(--border)"
                  fill="transparent"
                  strokeWidth={stroke}
                  r={normalizedRadius}
                  cx="52"
                  cy="52"
                />
                <circle
                  stroke="var(--success)"
                  fill="transparent"
                  strokeWidth={stroke}
                  strokeDasharray={circumference + ' ' + circumference}
                  style={{ strokeDashoffset, transition: 'stroke-dashoffset 0.5s ease-in-out' }}
                  strokeLinecap="round"
                  r={normalizedRadius}
                  cx="52"
                  cy="52"
                />
              </svg>
              <div className="score-text">
                <span>{prob}%</span>
                <small>recovery likelihood</small>
              </div>
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">Decision engine</p>
                <h2>Why this case is in review</h2>
              </div>
              <span className="ai-tag">
                <Sparkles className="size-3" />
                AI assisted
              </span>
            </div>
            <div className="reason-box">
              <div className="reason-icon">
                <CreditCard className="size-5" />
              </div>
              <div>
                <h3>{reason}</h3>
                <p>
                  {caseData.decisionReason ||
                    'PayBack is analyzing this customer’s payment pattern and sequencing recovery actions.'}
                </p>
              </div>
            </div>
          </div>

          {/* Escalation Card */}
          {caseData.status === 'escalated' && (
            <div className="panel" style={{ border: '2px solid rgba(245, 158, 11, 0.5)', background: 'rgba(245, 158, 11, 0.1)' }}>
              <div className="panel-heading">
                <p className="section-kicker" style={{ color: 'rgba(245, 158, 11, 0.9)' }}>Escalation Required</p>
                <h2>Human Review Needed</h2>
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ marginBottom: '12px' }}>
                  <strong>Reason:</strong> {caseData.escalateReason ? caseData.escalateReason.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Manual review required'}
                </div>
                <div style={{ marginBottom: '12px' }}>
                  <strong>Payment Amount:</strong> {formatINR(amount)}
                </div>
                <div style={{ marginBottom: '12px' }}>
                  <strong>Customer:</strong> {customerDisplayName}
                </div>
                <div style={{ marginBottom: '16px' }}>
                  <strong>Why:</strong> {caseData.decisionReason || 'This case requires human review due to policy or high-value thresholds.'}
                </div>
                <div style={{ padding: '12px', background: 'rgba(245, 158, 11, 0.15)', borderRadius: '6px', marginBottom: '16px', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                  <strong>Next step:</strong> A human reviewer should review the payment and customer history before another recovery action is attempted.
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Link href={`/customers/${caseData.customerId}`} className="button-secondary" style={{ fontSize: '13px' }}>
                    Open Customer
                  </Link>
                  <button className="button-secondary" style={{ fontSize: '13px' }} disabled>
                    View Payment
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="panel">
            <div className="panel-heading">
              <h2>Recovery timeline</h2>
              <span className="text-sm text-muted-foreground">
                {timeline.length} events
              </span>
            </div>
            <div className="timeline">
              {timeline.length > 0 ? (
                timeline.map((t, idx) => {
                  const human = formatAuditRecord(t)
                  return (
                    <div key={t.id || idx}>
                      <span className="timeline-dot done">
                        <Check className="size-3" />
                      </span>
                      <div>
                        <b>{human.title}</b>
                        <p>{human.description}</p>
                      </div>
                    </div>
                  )
                })
              ) : (
                <p className="text-muted-foreground p-4">No audit events recorded yet.</p>
              )}
            </div>
          </div>
        </div>
        <aside className="detail-side">
          <div className="panel">
            <p className="section-kicker">Customer</p>
            <div className="customer-profile">
              <div className="avatar large">
                {customerDisplayName.split(' ').map((x: string) => x[0]).join('').toUpperCase().slice(0, 2)}
              </div>
              <div>
                <h3>{customerDisplayName}</h3>
                <p>{customerEmailDisplay}</p>
              </div>
            </div>
            <div className="side-row">
              <span>Lifetime value</span>
              <b>{formatINR(customerMetrics?.totalPaidAmount ?? amount)}</b>
            </div>
            <div className="side-row">
              <span>Recovery cases</span>
              <b>{customerMetrics?.recoveryCasesCount ?? 1}</b>
            </div>
          </div>
          <div className="panel">
            <p className="section-kicker">Message preview</p>
            <div className="message-preview">
              <p>Hi {customerDisplayName.split(' ')[0]},</p>
              <p>
                We noticed a payment of {formatINR(amount)} couldn't be completed. You can securely complete your payment in just a moment.
              </p>
              <p>— The PayBack team</p>
            </div>
          </div>
        </aside>
      </div>
    </>
  )
}


function Analytics() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [trends, setTrends] = useState<DashboardTrends | null>(null)
  const [breakdown, setBreakdown] = useState<DashboardBreakdown | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        const [sum, tr, bd] = await Promise.all([
          dashboardService.getDashboardSummary(),
          dashboardService.getDashboardTrends(),
          dashboardService.getDashboardBreakdown(),
        ])
        if (!mounted) return
        setSummary(sum)
        setTrends(tr)
        setBreakdown(bd)
      } catch (err) {
        console.error('Failed to load analytics:', err)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const avgTime = summary ? `${summary.averageRecoveryTimeHours} days` : '—'
  const totalCases = summary ? summary.totalRecoveryCases : 0
  const successRate = summary ? `${(summary.overallRecoveryRate * 100).toFixed(1)}%` : '—'
  const recovered = summary ? formatINR(summary.totalRecoveredRevenue) : '—'

  // Find best performing action from breakdown
  const bestAction = breakdown?.byAction?.length
    ? breakdown.byAction.reduce((best, cur) => (cur.successRate > best.successRate ? cur : best), breakdown.byAction[0])
    : null
  const bestActionName = bestAction ? bestAction.action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Email'
  const bestActionRate = bestAction ? `${(bestAction.successRate * 100).toFixed(1)}%` : '—'

  return (
    <>
      <PageIntro title="Analytics" subtitle="Understand what is driving recovery performance." />
      <div className="metric-grid">
        <Metric label="Avg. time to recover" value={avgTime} change="16.0%" note="Faster than last month" />
        <Metric label="Best performing action" value={bestActionName} change={bestActionRate} note={`${bestActionRate} success rate`} />
        <Metric label="Total cases processed" value={totalCases.toString()} change="21.4%" note="All time" />
        <Metric label="Overall recovery rate" value={successRate} change="4.8%" note="Across all channels" />
      </div>
      <div className="dashboard-grid">
        <div className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Recovery trend</p>
              <h2>Revenue recovered over time</h2>
            </div>
          </div>
          {trends && trends.trends.length > 0 ? (
            <div className="chart-wrap">
              <div className="chart-y">
                {(() => {
                  const maxVal = Math.max(...trends.trends.map(t => t.recoveredAmount), 1)
                  return [1, 0.75, 0.5, 0.25, 0].map((f) => (
                    <span key={f}>{formatINR(Math.round(maxVal * f))}</span>
                  ))
                })()}
              </div>
              <div className="chart-grid">
                {trends.trends.map((t, i) => {
                  const maxVal = Math.max(...trends.trends.map(tr => tr.recoveredAmount), 1)
                  return <div key={i} className="chart-bar" style={{ height: `${(t.recoveredAmount / maxVal) * 100}%` }} title={`${t.date}: ${formatINR(t.recoveredAmount)}`} />
                })}
              </div>
              <div className="chart-x">
                {(() => {
                  const totalDataPoints = trends.trends.length
                  const maxLabelsToShow = 6  // Show at most 6 date labels
                  const stepSize = Math.max(1, Math.floor(totalDataPoints / maxLabelsToShow))
                  
                  return trends.trends.map((t, i) => (
                    // Only show date labels at regular intervals to avoid overcrowding
                    i % stepSize === 0 || i === totalDataPoints - 1 ? (
                      <span key={i}>{t.date.slice(5)}</span>
                    ) : null
                  )).filter(Boolean)
                })()}
              </div>
            </div>
          ) : (
            <MiniChart trends={null} />
          )}
        </div>
        <div className="panel breakdown">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Breakdown</p>
              <h2>Recovery by action</h2>
            </div>
          </div>
          <div className="donut">
            <div>
              <strong>{successRate}</strong>
              <span>recovered</span>
            </div>
          </div>
          <div className="channel-list">
            {breakdown?.byAction?.length ? (
              breakdown.byAction.map((a, i) => (
                <div key={a.action}>
                  <span>
                    <i className={`dot ${i === 0 ? 'bg-primary' : i === 1 ? 'bg-success' : 'bg-warning'}`} />
                    {a.action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                  <b>{a.count} cases · {formatINR(a.recoveredAmount)}</b>
                </div>
              ))
            ) : (
              <>
                <div><span><i className="dot bg-primary" />Payment Link</span><b>—</b></div>
                <div><span><i className="dot bg-success" />Smart Retry</span><b>—</b></div>
              </>
            )}
          </div>
        </div>
      </div>
      {breakdown?.byStatus && Object.keys(breakdown.byStatus).length > 0 && (
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Status distribution</p>
              <h2>Cases by status</h2>
            </div>
          </div>
          <div className="channel-list" style={{ padding: '16px' }}>
            {Object.entries(breakdown.byStatus).map(([status, count]) => (
              <div key={status}>
                <span>
                  <i className={`dot ${status === 'recovered' ? 'bg-success' : status === 'detected' || status === 'in_review' ? 'bg-warning' : 'bg-primary'}`} />
                  {status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
                <b>{count}</b>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

function Customers() {
  const [customerList, setCustomerList] = useState<ApiCustomer[]>([])
  const [recentFailures, setRecentFailures] = useState<RecoveryCase[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        // Optimized: Parallelize customer and recovery data fetching
        const [apiCusts, recoveries] = await Promise.all([
          customersService.listCustomers({ limit: 100 }),
          recoveriesService.listRecoveries({ limit: 10 }),
        ])
        if (!mounted) return
        
        // Filter recent failed payments
        const failedPayments = recoveries.filter(
          (r) => r.status === 'detected' || r.status === 'failed' || r.status === 'in_review'
        )
        setRecentFailures(failedPayments)
        setCustomerList(apiCusts)
      } catch (err) {
        console.error('Failed to load customers:', err)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const filtered = customerList.filter((c) =>
    !searchQuery ||
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (c.email && c.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
    c.id.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <>
      <PageIntro 
        title="Customers" 
        subtitle="A clear view of customers with payment activity." 
      />
      <div className="table-card">
        <div className="table-heading">
          <div className="search">
            <Search className="size-4 text-muted-foreground" />
            <input
              placeholder="Search customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Lifetime value</th>
                <th>Open cases</th>
                <th>Joined</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <>
                  {[1, 2, 3].map((n) => (
                    <tr key={n}>
                      <td colSpan={5} className="text-muted-foreground text-center py-4">
                        Loading customer records...
                      </td>
                    </tr>
                  ))}
                </>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center text-muted-foreground py-6">
                    {searchQuery ? 'No matching customers found' : 'No customers recorded yet'}
                  </td>
                </tr>
              ) : (
                filtered.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link href={`/customers/${c.id}`} className="customer-link">
                        <div className="avatar small">{c.name.split(' ').map((x: string) => x[0]).join('').toUpperCase().slice(0, 2)}</div>
                        <span>
                          <b>{c.name}</b>
                          <small>{c.email || `${c.id}@example.com`}</small>
                        </span>
                      </Link>
                    </td>
                    <td>{formatINR(c.totalPaidAmount ?? 0)}</td>
                    <td>
                      {(c.openRecoveryCases ?? 0) > 0 ? (
                        <span className="status status-warn">{c.openRecoveryCases} open</span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </td>
                    <td className="text-muted-foreground">
                      {c.createdAt ? new Date(c.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'N/A'}
                    </td>
                    <td>
                      <Link href={`/customers/${c.id}`} className="icon-btn" aria-label="View customer">
                        <ChevronRight className="size-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Recent Payment Failures Section */}
      {recentFailures.length > 0 && (
        <div className="panel" style={{ marginTop: '24px' }}>
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Alerts</p>
              <h2>Recent Payment Failures</h2>
            </div>
            <span className="status status-bad">{recentFailures.length} Failed</span>
          </div>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Reason</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {recentFailures.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link href={`/recoveries/${r.id}`} className="customer-link">
                        <b>{r.customerId.replace('cus_', '').replace(/_/g, ' ')}</b>
                        <small>{r.customerId}</small>
                      </Link>
                    </td>
                    <td>{formatINR(r.amountAtRisk)}</td>
                    <td>
                      <span className="status status-bad">Failed</span>
                    </td>
                    <td className="text-muted-foreground">{r.reason}</td>
                    <td className="text-muted-foreground">
                      {new Date(r.createdAt).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}

function CustomerDetail({ id }: { id: string }) {
  const [detail, setDetail] = useState<ApiCustomerDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(null)
    async function load() {
      try {
        const d = await customersService.getCustomerDetail(id)
        if (!mounted) return
        setDetail(d)
      } catch (err) {
        if (!mounted) return
        console.error('Failed to load customer detail:', err)
        setError(err instanceof Error ? err.message : 'Customer not found')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [id])

  if (loading) {
    return (
      <>
        <Link href="/customers" className="back-link">
          ← Back to customers
        </Link>
        <PageIntro
          title="Loading customer..."
          subtitle="Fetching account history and recovery performance..."
        />
        <div className="metric-grid">
          <Metric label="Lifetime value" value="—" change="Live" note="Calculating..." />
          <Metric label="Recovery rate" value="—" change="Live" note="Customer score" />
          <Metric label="Open recoveries" value="—" change="Live" note="Queue status" />
          <Metric label="Total payments" value="—" change="Live" note="Activity" />
        </div>
        <div className="dashboard-grid">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">Payment history</p>
                <h2>Recent payments</h2>
              </div>
            </div>
            <p className="text-muted-foreground p-6 text-center">Loading transactions...</p>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">Activity</p>
                <h2>Customer timeline</h2>
              </div>
            </div>
            <p className="text-muted-foreground p-6 text-center">Loading timeline...</p>
          </div>
        </div>
      </>
    )
  }

  if (error || !detail) {
    return (
      <>
        <Link href="/customers" className="back-link">
          ← Back to customers
        </Link>
        <div className="panel" style={{ padding: '32px', textAlign: 'center' }}>
          <h2>Customer Record Not Found</h2>
          <p className="text-muted-foreground mt-2 mb-4">
            {error || `No customer was found with ID '${id}' in your workspace.`}
          </p>
          <Link href="/customers" className="button-primary">
            Return to Customers
          </Link>
        </div>
      </>
    )
  }

  const { customer, metrics, recentTransactions, recentRecoveries } = detail
  const lifetime = metrics.totalPaidAmount
  const recoveryRate = Math.round(metrics.recoveryRate * 100)
  const openCases = metrics.recoveryCasesCount - metrics.successfulRecoveriesCount

  return (
    <>
      <Link href="/customers" className="back-link">
        ← Back to customers
      </Link>
      <PageIntro
        title={customer.name}
        subtitle={`${customer.email || `${customer.id}@example.com`} · Customer since ${customer.createdAt ? new Date(customer.createdAt).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) : 'N/A'}`}
        action={<span className="status status-neutral">{customer.id}</span>}
      />
      <div className="metric-grid">
        <Metric label="Lifetime value" value={formatINR(lifetime)} change="Live" note={`${metrics.successfulPayments} paid`} />
        <Metric label="Recovery rate" value={`${recoveryRate}%`} change="Live" note="Customer success score" />
        <Metric label="Open recoveries" value={Math.max(0, openCases).toString()} change="Live" note="Needs attention" positive={openCases === 0} />
        <Metric label="Total transactions" value={metrics.totalPayments.toString()} change="Live" note={`${metrics.failedPayments} failed`} />
      </div>
      <div className="dashboard-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Payment history</p>
              <h2>Recent payments</h2>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Payment</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {recentTransactions.length > 0 ? (
                  recentTransactions.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <b>{p.id.slice(0, 16)}</b>
                      </td>
                      <td>{formatINR(p.amount)}</td>
                      <td className="text-muted-foreground">{p.paymentMethod ? p.paymentMethod.replace(/_/g, ' ') : 'UPI'}</td>
                      <td>
                        <span className={`status ${p.status === 'success' ? 'status-good' : p.status === 'pending' ? 'status-neutral' : 'status-bad'}`}>
                          {p.status.charAt(0).toUpperCase() + p.status.slice(1)}
                        </span>
                      </td>
                      <td className="text-muted-foreground">
                        {p.createdAt ? new Date(p.createdAt).toLocaleDateString() : 'Today'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="text-center text-muted-foreground py-6">No payments recorded for this customer</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Activity</p>
              <h2>Customer overview</h2>
            </div>
          </div>
          <div className="customer-profile">
            <div className="avatar large">
              {customer.name.split(' ').map((x: string) => x[0]).join('').toUpperCase().slice(0, 2)}
            </div>
            <div>
              <h3>{customer.name}</h3>
              <p>{customer.email || 'No email recorded'}</p>
              <p className="text-xs text-muted-foreground mt-1">{customer.phone || 'No phone recorded'}</p>
            </div>
          </div>
          <div className="side-row">
            <span>Customer ID</span>
            <b style={{ fontSize: '11px' }}>{customer.id}</b>
          </div>
          <div className="side-row">
            <span>Historical success</span>
            <b>{Math.round(metrics.historicalSuccessRate * 100)}%</b>
          </div>
          <div className="side-row">
            <span>Recovered revenue</span>
            <b>{formatINR(metrics.recoveredRevenue)}</b>
          </div>
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Recovery history</p>
            <h2>Linked recovery cases</h2>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {recentRecoveries.length > 0 ? (
                recentRecoveries.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link href={`/recoveries/${r.id}`} className="customer-link">
                        <b>{r.id.slice(0, 16)}</b>
                      </Link>
                    </td>
                    <td>{formatINR(r.amountAtRisk)}</td>
                    <td>
                      <Status status={formatRecoveryStatus(r.status)} />
                    </td>
                    <td className="text-muted-foreground">{r.reason}</td>
                    <td className="text-muted-foreground">{new Date(r.createdAt).toLocaleDateString()}</td>
                    <td>
                      <Link href={`/recoveries/${r.id}`} className="icon-btn" aria-label="View case">
                        <ChevronRight className="size-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="text-center text-muted-foreground py-6">No recovery cases for this customer</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}


function PoliciesPage({
  policiesList,
  onCreatePolicy,
  onEditPolicy,
}: {
  policiesList: Policy[]
  onCreatePolicy: () => void
  onEditPolicy: (p: Policy) => void
}) {
  const activeCount = policiesList.filter((p) => p.status === 'Active').length

  return (
    <>
      <PageIntro
        title="Policies"
        subtitle="Automate the right recovery action for every situation."
        action={
          <button className="button-primary" onClick={onCreatePolicy}>
            <Plus className="size-4" />
            Create policy
          </button>
        }
      />
      <div className="metric-grid">
        <Metric label="Active policies" value={activeCount.toString()} change="100%" note="Automated guardrails" />
        <Metric label="Max retries default" value="3" change="0" note="Per failed invoice" />
        <Metric label="Recovery window" value="72h" change="0" note="Standard duration" />
        <Metric label="High-value threshold" value="₹10,000" change="Safe" note="Requires human review" />
      </div>
      <div className="settings-grid">
        {policiesList.map((p) => (
          <div className="panel setting-item" key={p.id} onClick={() => onEditPolicy(p)}>
            <div className="setting-icon">
              <ShieldCheck className="size-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3>{p.name}</h3>
                <span className={`status ${p.status === 'Active' ? 'status-good' : 'status-warn'}`}>
                  {p.status}
                </span>
              </div>
              <p>{p.description}</p>
              <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                <span>Max Retries: <b>{p.maxRetries}</b></span>
                <span>Window: <b>{p.recoveryWindowHours}h</b></span>
                <span>High-value: <b>{formatINR(p.highValueThreshold)}</b></span>
              </div>
            </div>
            <button className="button-secondary shrink-0" onClick={(e) => { e.stopPropagation(); onEditPolicy(p) }}>
              Edit
            </button>
          </div>
        ))}
      </div>
    </>
  )
}

function SettingsPage({
  settings,
  onOpenDialog,
}: {
  settings: WorkspaceSettings
  onOpenDialog: (kind: 'workspace' | 'notifications' | 'account') => void
}) {
  return (
    <>
      <PageIntro title="Settings" subtitle="Manage your workspace preferences, recovery alerts, and account configurations." />
      
      {/* Top summary overview cards */}
      <div className="metric-grid">
        <Metric label="Active Workspace" value={settings.workspaceName} change="Active" note={settings.timezone.split(' ')[0]} />
        <Metric label="Recovery Alerts" value="4 Active" change="100%" note="Email & App triggers" />
        <Metric label="Environment" value="Production" change="v1.0" note="FastAPI + Supabase" />
        <Metric label="Role" value="Workspace Admin" change="Full" note="aditi@payback.io" />
      </div>

      <div className="settings-grid">
        <div className="panel setting-item" onClick={() => onOpenDialog('workspace')}>
          <div className="setting-icon">
            <ShieldCheck className="size-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3>Workspace Preferences</h3>
              <span className="status status-good">Configured</span>
            </div>
            <p>Manage your merchant organization name ({settings.workspaceName}) and default timezone ({settings.timezone}).</p>
          </div>
          <button className="button-secondary shrink-0" onClick={(e) => { e.stopPropagation(); onOpenDialog('workspace') }}>
            Configure
          </button>
        </div>

        <div className="panel setting-item" onClick={() => onOpenDialog('notifications')}>
          <div className="setting-icon">
            <Bell className="size-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3>Notification & Alert Channels</h3>
              <span className="status status-good">Active</span>
            </div>
            <p>Manage real-time notifications for payment recovered events, case escalations, and webhook failures.</p>
          </div>
          <button className="button-secondary shrink-0" onClick={(e) => { e.stopPropagation(); onOpenDialog('notifications') }}>
            Configure
          </button>
        </div>

        <div className="panel setting-item" onClick={() => onOpenDialog('account')}>
          <div className="setting-icon">
            <Users className="size-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3>Account & Profile</h3>
              <span className="status status-warn">Admin</span>
            </div>
            <p>View current authenticated merchant credentials, API keys status, and manage session logout.</p>
          </div>
          <button className="button-secondary shrink-0" onClick={(e) => { e.stopPropagation(); onOpenDialog('account') }}>
            View
          </button>
        </div>
      </div>
    </>
  )
}


export default function PayBackApp({ view = 'dashboard', id }: { view?: string; id?: string }) {
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [dark, setDark] = useState(true)
  const [ready, setReady] = useState(false)

  // Local state abstractions with live service syncing
  const [recoveriesList, setRecoveriesList] = useState<Recovery[]>([])
  const [customersList, setCustomersList] = useState<ApiCustomer[]>([])
  const [policiesList, setPoliciesList] = useState<Policy[]>(initialPolicies)
  const [notifsList, setNotifsList] = useState<Notification[]>(initialNotifications)
  const [settingsState, setSettingsState] = useState<WorkspaceSettings>(initialSettings)

  // Modals state
  const [recoveryModalOpen, setRecoveryModalOpen] = useState(false)
  const [paymentModalOpen, setPaymentModalOpen] = useState(false)
  const [policyModalOpen, setPolicyModalOpen] = useState(false)
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null)
  const [settingsModalKind, setSettingsModalKind] = useState<'workspace' | 'notifications' | 'account' | null>(null)

  const [currentUser, setCurrentUser] = useState<{ name: string; email: string; merchantId?: string } | null>(null)

  useEffect(() => {
    const savedTheme = window.localStorage.getItem('payback-theme')
    if (savedTheme) setDark(savedTheme === 'dark')
    const session = getAuthSession()
    if (!session) {
      router.replace('/sign-in')
    } else {
      setCurrentUser(session)
      // For demo/admin user, provide demo notification history if backend has none
      if (session.email.includes('admin') || session.email.includes('demo')) {
        setNotifsList(initialNotifications)
      } else {
        setNotifsList([])
      }
    }
    setReady(true)
  }, [router])

  // Load live data on mount
  useEffect(() => {
    let mounted = true
    async function loadData() {
      try {
        // Optimized: Parallelize all independent API calls on initial load
        const [pols, notifs, profile, notifSet, recs, custs] = await Promise.allSettled([
          policiesService.listPolicies(),
          notifService.listNotifications(),
          settingsService.getProfile(),
          settingsService.getNotificationSettings(),
          recoveriesService.listRecoveries(),
          customersService.listCustomers(),
        ])

        if (!mounted) return

        const customerMap = new Map<string, { name: string; email: string }>()
        if (custs.status === 'fulfilled') {
          custs.value.forEach((c) => {
            customerMap.set(c.id, { name: c.name, email: c.email || `${c.id}@example.com` })
          })
          setCustomersList(custs.value)
        }

        if (pols.status === 'fulfilled' && pols.value.length > 0) {
          setPoliciesList(
            pols.value.map((p) => ({
              id: p.id,
              name: p.name,
              description: 'Automated recovery sequence policy',
              status: p.isActive ? 'Active' : 'Draft',
              maxRetries: p.maximumRetries,
              maxMessages: p.maximumMessages,
              recoveryWindowHours: p.recoveryWindowHours,
              highValueThreshold: p.highValueThreshold,
              humanApprovalRequired: p.humanApprovalRequired,
            }))
          )
        }

        if (notifs.status === 'fulfilled' && notifs.value.length > 0) {
          setNotifsList(
            notifs.value.map((n) => ({
              id: n.id,
              type: (n.notificationType as any) || 'payment_recovered',
              title: n.title,
              message: n.message,
              time: 'Just now',
              read: n.read,
            }))
          )
        }

        if (profile.status === 'fulfilled' && profile.value) {
          setSettingsState((prev) => ({
            ...prev,
            workspaceName: profile.value.name || prev.workspaceName,
            timezone: profile.value.timezone || prev.timezone,
          }))
          setCurrentUser((prev) => ({
            name: profile.value.name || prev?.name || 'Workspace Admin',
            email: profile.value.email || prev?.email || 'admin@payback.io',
            merchantId: profile.value.id || prev?.merchantId,
          }))
        }

        if (recs.status === 'fulfilled' && recs.value.length > 0) {
          setRecoveriesList(
            recs.value.map((r) => {
              const custInfo = customerMap.get(r.customerId)
              const custName = custInfo?.name || (r.customerId.includes('-') ? 'Rahul Verma' : r.customerId.replace('cus_', '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()))
              const custEmail = custInfo?.email || 'customer@example.com'
              return {
                id: r.id,
                customerId: r.customerId,
                customer: custName,
                email: custEmail,
                amount: r.amountAtRisk,
                status: formatRecoveryStatus(r.status),
                reason: r.reason,
                created: 'Today, ' + new Date(r.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                payment: 'UPI ·•• 4821',
                probability: Math.round(r.recoveryProbability * 100),
                nextAction: r.selectedAction ? r.selectedAction.replace(/_/g, ' ') : 'Send reminder',
              }
            })
          )
        }
      } catch (err) {
        console.error('Error syncing initial app state:', err)
      }
    }
    loadData()
    return () => { mounted = false }
  }, [])


  useEffect(() => {
    if (ready) {
      window.localStorage.setItem('payback-theme', dark ? 'dark' : 'light')
    }
  }, [dark, ready])

  if (!ready || !getAuthSession()) return null

  async function handleCreateRecovery(rec: Omit<Recovery, 'id' | 'created' | 'probability' | 'nextAction'>) {
    try {
      const createdCase = await recoveriesService.recordFailedPayment({
        customer_name: rec.customer,
        customer_email: rec.email,
        transaction_amount: rec.amount,
        payment_method: rec.payment,
        failure_reason: rec.reason,
      })

      // Run recovery agent on the newly created case
      try {
        await recoveriesService.startRecovery({ case_id: createdCase.id })
      } catch (err) {
        console.warn('Auto start recovery notice:', err)
      }

      // Re-fetch all data to ensure dashboard and tables update live
      const [updatedRecs, updatedCusts] = await Promise.all([
        recoveriesService.listRecoveries(),
        customersService.listCustomers(),
      ])

      const customerMap = new Map<string, { name: string; email: string }>()
      updatedCusts.forEach((c) => {
        customerMap.set(c.id, { name: c.name, email: c.email || `${c.id}@example.com` })
      })

      if (updatedRecs.length > 0) {
        setRecoveriesList(
          updatedRecs.map((r) => {
            const custInfo = customerMap.get(r.customerId)
            return {
              id: r.id,
              customerId: r.customerId,
              customer: custInfo?.name || rec.customer,
              email: custInfo?.email || rec.email,
              amount: r.amountAtRisk,
              status: formatRecoveryStatus(r.status),
              reason: r.reason,
              created: 'Just now',
              payment: rec.payment,
              probability: Math.round(r.recoveryProbability * 100),
              nextAction: r.selectedAction ? r.selectedAction.replace(/_/g, ' ') : 'Smart retry',
            }
          })
        )
      }
    } catch (err) {
      console.error('Failed to create real recovery case:', err)
      throw err
    }
  }

  async function handleCreatePayment(customerData: CreatePaymentWithCustomerRequest): Promise<CreatePaymentResponse> {
    try {
      const paymentResult: CreatePaymentResponse = await paymentsService.createPaymentWithCustomer(customerData)

      // Refresh customer data to show new customer
      const updatedCusts = await customersService.listCustomers()
      setCustomersList(updatedCusts)

      // Show success message (in real app, this would be a toast)
      console.log('Payment created successfully:', paymentResult)
      
      return paymentResult
    } catch (err) {
      console.error('Failed to create payment:', err)
      throw err
    }
  }

  async function handleSavePolicy(pol: Omit<Policy, 'id'>, existingId?: string) {
    try {
      if (existingId) {
        await policiesService.updatePolicy(existingId, {
          name: pol.name,
          isActive: pol.status === 'Active',
          maximumRetries: pol.maxRetries,
          maximumMessages: pol.maxMessages,
          recoveryWindowHours: pol.recoveryWindowHours,
          highValueThreshold: pol.highValueThreshold,
          humanApprovalRequired: pol.humanApprovalRequired,
        })
      } else {
        await policiesService.createPolicy({
          name: pol.name,
          isActive: pol.status === 'Active',
          maximumRetries: pol.maxRetries,
          maximumMessages: pol.maxMessages,
          recoveryWindowHours: pol.recoveryWindowHours,
          highValueThreshold: pol.highValueThreshold,
          humanApprovalRequired: pol.humanApprovalRequired,
        })
      }
      const updatedPols = await policiesService.listPolicies()
      setPoliciesList(
        updatedPols.map((p) => ({
          id: p.id,
          name: p.name,
          description: 'Automated recovery sequence policy',
          status: p.isActive ? 'Active' : 'Draft',
          maxRetries: p.maximumRetries,
          maxMessages: p.maximumMessages,
          recoveryWindowHours: p.recoveryWindowHours,
          highValueThreshold: p.highValueThreshold,
          humanApprovalRequired: p.humanApprovalRequired,
        }))
      )
    } catch {
      if (existingId) {
        updatePolicy(existingId, pol)
      }
      setPoliciesList([...initialPolicies])
    }
  }

  async function handleMarkNotifRead(notifId: string) {
    try {
      await notifService.markNotificationRead(notifId)
    } catch {
      markNotificationRead(notifId)
    }
    setNotifsList((prev) => prev.map((n) => (n.id === notifId ? { ...n, read: true } : n)))
  }

  async function handleMarkAllNotifsRead() {
    try {
      await notifService.markAllNotificationsRead()
    } catch {
      markAllNotificationsRead()
    }
    setNotifsList((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  async function handleUpdateSettings(updates: Partial<WorkspaceSettings>) {
    try {
      if (updates.workspaceName || updates.timezone) {
        await settingsService.updateProfile({
          name: updates.workspaceName,
          timezone: updates.timezone,
        })
      }
      await settingsService.updateNotificationSettings({
        notifyRecoveryCompleted: updates.notifyRecoveryCompleted,
        notifyRecoveryEscalated: updates.notifyRecoveryEscalated,
        notifyActionFailed: updates.notifyActionFailed,
        notifyPaymentRecovered: updates.notifyPaymentRecovered,
      })
    } catch {
      updateWorkspaceSettings(updates)
    }
    setSettingsState((prev) => ({ ...prev, ...updates }))
  }


  let content: React.ReactNode
  if (view === 'recoveries') {
    content = <Recoveries recoveriesList={recoveriesList} onNewRecovery={() => setRecoveryModalOpen(true)} />
  } else if (view === 'detail') {
    content = <Detail id={id ?? ''} />
  } else if (view === 'analytics') {
    content = <Analytics />
  } else if (view === 'customers') {
    content = <Customers />
  } else if (view === 'customer-detail') {
    content = <CustomerDetail id={id ?? ''} />
  } else if (view === 'policies') {
    content = (
      <PoliciesPage
        policiesList={policiesList}
        onCreatePolicy={() => {
          setSelectedPolicy(null)
          setPolicyModalOpen(true)
        }}
        onEditPolicy={(p) => {
          setSelectedPolicy(p)
          setPolicyModalOpen(true)
        }}
      />
    )
  } else if (view === 'settings') {
    content = <SettingsPage settings={settingsState} onOpenDialog={(kind) => setSettingsModalKind(kind)} />
  } else {
    content = <Dashboard user={currentUser} />
  }

  return (
    <div className={`app ${dark ? 'theme-dark' : 'theme-light'}`}>
      <Sidebar
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        mobile={mobile}
        onNavigate={() => setMobile(false)}
        user={currentUser}
      />
      <div className={`mobile-overlay ${mobile ? 'show' : ''}`} onClick={() => setMobile(false)} />
      <main className="main">
        <Header
          onMenu={() => setMobile(true)}
          dark={dark}
          setDark={setDark}
          collapsed={collapsed}
          setCollapsed={setCollapsed}
          notifs={notifsList}
          onMarkRead={handleMarkNotifRead}
          onMarkAllRead={handleMarkAllNotifsRead}
          onNewPayment={() => setPaymentModalOpen(true)}
        />
        <div className="content">{content}</div>
      </main>

      {/* Dialog Modals */}
      <NewRecoveryDialog
        open={recoveryModalOpen}
        onClose={() => setRecoveryModalOpen(false)}
        onCreate={handleCreateRecovery}
      />
      <NewPaymentDialog
        open={paymentModalOpen}
        onClose={() => setPaymentModalOpen(false)}
        onCreate={handleCreatePayment}
      />
      <PolicyDialog
        open={policyModalOpen}
        policy={selectedPolicy}
        onClose={() => {
          setPolicyModalOpen(false)
          setSelectedPolicy(null)
        }}
        onSave={handleSavePolicy}
      />
      <SettingsDialog
        open={settingsModalKind !== null}
        kind={settingsModalKind}
        settings={settingsState}
        onClose={() => setSettingsModalKind(null)}
        onSave={handleUpdateSettings}
      />
    </div>
  )
}

export function Landing() {
  const [dark, setDark] = useState(true)

  useEffect(() => {
    const savedTheme = window.localStorage.getItem('payback-theme')
    if (savedTheme) setDark(savedTheme === 'dark')
  }, [])

  function toggleTheme() {
    const nextDark = !dark
    setDark(nextDark)
    window.localStorage.setItem('payback-theme', nextDark ? 'dark' : 'light')
  }

  return (
    <main className={`landing ${dark ? 'theme-dark' : 'theme-light'}`}>
      <div className="landing-grid-bg" aria-hidden="true" />
      
      <nav className="landing-nav">
        <Logo />
        <div className="flex items-center gap-3">
          <button
            className="icon-btn"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            title={dark ? 'Switch to Light mode' : 'Switch to Dark mode'}
          >
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          <Link href="/sign-in" className="button-ghost">
            Sign in
          </Link>
          <Link href="/sign-up" className="button-primary">
            Get started <ChevronRight className="size-4" />
          </Link>
        </div>
      </nav>

      <section className="landing-hero">
        <div className="hero-copy">
          <span className="eyebrow-pill">
            <span className="size-1.5 rounded-full bg-success" />
            Automated Payment Recovery
          </span>
          <h1>
            Turn failed payments into <em>recovered revenue.</em>
          </h1>
          <p>
            PayBack sequences intelligent payment retries and gentle customer reminders through email and WhatsApp — protecting
            merchant revenue without damaging customer relationships.
          </p>
          <div className="hero-actions">
            <Link href="/dashboard" className="button-primary large">
              Explore the dashboard <ChevronRight className="size-4" />
            </Link>
            <Link href="/sign-in" className="button-ghost large">
              Sign in to workspace
            </Link>
          </div>
        </div>

        <div className="product-preview">
          <div className="preview-top">
            <span className="preview-dot" />
            <span className="preview-dot" />
            <span className="preview-dot" />
            <span className="preview-title">PayBack / overview</span>
          </div>
          <div className="preview-inner">
            <div className="preview-side">
              <div className="mini-logo">
                <Sparkles className="size-3" />
              </div>
              <span className="mini-line active" />
              <span className="mini-line" />
              <span className="mini-line" />
              <span className="mini-line short" />
            </div>
            <div className="preview-content">
              <p className="section-kicker">Live Dashboard</p>
              <h3>Recovery Performance</h3>
              <div className="preview-metrics">
                <div>
                  <small>Recovered</small>
                  <b>₹1.84L</b>
                  <i>+18.2%</i>
                </div>
                <div>
                  <small>Recovery rate</small>
                  <b>68.4%</b>
                  <i>+4.8%</i>
                </div>
              </div>
              <div className="preview-bars">
                {chartData.slice(0, 9).map((v, i) => (
                  <span key={i} style={{ height: `${v}%` }} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}


