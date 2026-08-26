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
  addPolicy,
  addRecovery,
  chartData,
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
import { clearDemoSession, getDemoSession } from '@/lib/demo-session'

const nav = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/recoveries', label: 'Recoveries', icon: Activity, count: '126' },
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


function Status({ status }: { status: RecoveryStatus }) {
  const styles: Record<RecoveryStatus, string> = {
    Recovered: 'status-good',
    'In review': 'status-warn',
    Failed: 'status-bad',
  }
  return (
    <span className={`status ${styles[status] ?? 'status-warn'}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </span>
  )
}

function Sidebar({
  collapsed,
  setCollapsed,
  mobile,
  onNavigate,
}: {
  collapsed: boolean
  setCollapsed: (v: boolean | ((prev: boolean) => boolean)) => void
  mobile: boolean
  onNavigate?: () => void
}) {
  const pathname = usePathname()
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
        {nav.map(({ href, label, icon: Icon, count }) => (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={`nav-link ${pathname.startsWith(href) ? 'nav-active' : ''}`}
            title={collapsed ? label : undefined}
          >
            <Icon className="size-[18px] shrink-0" />
            {!collapsed && (
              <>
                <span>{label}</span>
                {count && <span className="nav-count">{count}</span>}
              </>
            )}
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
          <div className="avatar">AS</div>
          {!collapsed && (
            <div>
              <b>Aditi Sharma</b>
              <span>admin@payback.io</span>
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
                    clearDemoSession()
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
}: {
  onMenu: () => void
  dark: boolean
  setDark: (v: boolean) => void
  collapsed: boolean
  setCollapsed: (v: boolean | ((prev: boolean) => boolean)) => void
  notifs: Notification[]
  onMarkRead: (id: string) => void
  onMarkAllRead: () => void
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

function MiniChart() {
  return (
    <div className="chart-wrap">
      <div className="chart-y">
        <span>₹2.0L</span>
        <span>₹1.5L</span>
        <span>₹1.0L</span>
        <span>₹0.5L</span>
        <span>₹0</span>
      </div>
      <div className="chart-grid">
        {chartData.map((v, i) => (
          <div key={i} className="chart-bar" style={{ height: `${v}%` }} />
        ))}
      </div>
      <div className="chart-x">
        <span>Aug 01</span>
        <span>Aug 08</span>
        <span>Aug 15</span>
        <span>Aug 26</span>
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

  function handleExportCSV() {
    const headers = ['Case ID', 'Customer', 'Email', 'Amount (INR)', 'Status', 'Reason', 'Payment Method', 'Created']
    const rows = recoveriesList.map((r) => [
      r.id,
      `"${r.customer}"`,
      r.email,
      r.amount,
      r.status,
      `"${r.reason}"`,
      `"${r.payment}"`,
      `"${r.created}"`,
    ])
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `payback_recoveries_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
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
          <button className="button-secondary" onClick={handleExportCSV} title="Export recovery records to CSV">
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
                        {r.customer.split(' ').map((x) => x[0]).join('')}
                      </span>
                      <span>
                        <b>{r.customer}</b>
                        <small>{r.id}</small>
                      </span>
                    </Link>
                  </td>
                  <td className="font-medium">{formatINR(r.amount)}</td>
                  <td>
                    <Status status={r.status} />
                  </td>
                  <td className="text-muted-foreground">{r.reason}</td>
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
            <h2>New Recovery Case</h2>
            <p>Initiate automated revenue recovery for a failed transaction.</p>
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
              Create Recovery
            </button>
          </div>
        </form>
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

function Dashboard({ onNewRecovery }: { onNewRecovery: () => void }) {
  return (
    <>
      <PageIntro
        title="Overview"
        subtitle="Welcome back, Aditi. Here is your recovery performance."
        action={
          <button className="button-primary" onClick={onNewRecovery}>
            <Sparkles className="size-4" />
            New recovery
          </button>
        }
      />
      <div className="metric-grid">
        <Metric label="Recovered this month" value={formatINR(metrics.recovered)} change="18.2%" note="vs. ₹1.56L last month" />
        <Metric label="Recovery rate" value={`${metrics.recoveryRate}%`} change="4.8%" note="vs. 63.6% last month" />
        <Metric label="At risk" value={formatINR(metrics.atRisk)} change="8.1%" positive={false} note="Across 38 customers" />
        <Metric label="Active cases" value={metrics.activeCases.toString()} change="12.4%" note="12 need attention" />
      </div>
      <div className="dashboard-grid">
        <div className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Performance</p>
              <h2>Recovered revenue</h2>
            </div>
            <select className="select">
              <option>Last 30 days</option>
              <option>Last 90 days</option>
            </select>
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
          <MiniChart />
        </div>
        <div className="panel breakdown">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Breakdown</p>
              <h2>Recovery by channel</h2>
            </div>
            <MoreHorizontal className="size-5 text-muted-foreground" />
          </div>
          <div className="donut">
            <div>
              <strong>68.4%</strong>
              <span>recovered</span>
            </div>
          </div>
          <div className="channel-list">
            <div>
              <span>
                <i className="dot bg-primary" />
                Email
              </span>
              <b>52%</b>
            </div>
            <div>
              <span>
                <i className="dot bg-success" />
                WhatsApp
              </span>
              <b>31%</b>
            </div>
            <div>
              <span>
                <i className="dot bg-warning" />
                SMS
              </span>
              <b>17%</b>
            </div>
          </div>
        </div>
      </div>
      <RecoveryTable recoveriesList={initialRecoveries} compact />
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
  const [filter, setFilter] = useState<'All' | RecoveryStatus>('All')
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
        <button className={`filter ${filter === 'In review' ? 'active' : ''}`} onClick={() => setFilter('In review')}>
          In review <span>{recoveriesList.filter((r) => r.status === 'In review').length}</span>
        </button>
        <button className={`filter ${filter === 'Recovered' ? 'active' : ''}`} onClick={() => setFilter('Recovered')}>
          Recovered <span>{recoveriesList.filter((r) => r.status === 'Recovered').length}</span>
        </button>
        <button className={`filter ${filter === 'Failed' ? 'active' : ''}`} onClick={() => setFilter('Failed')}>
          Failed <span>{recoveriesList.filter((r) => r.status === 'Failed').length}</span>
        </button>
      </div>
      <RecoveryTable recoveriesList={filtered} />
    </>
  )
}

function Detail({ id }: { id: string }) {
  const r = getRecovery(id)
  const radius = 42
  const stroke = 6
  const normalizedRadius = radius - stroke * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - (r.probability / 100) * circumference

  return (
    <>
      <Link href="/recoveries" className="back-link">
        ← Back to recoveries
      </Link>
      <PageIntro title={r.customer} subtitle={`${r.id} · Created ${r.created}`} action={<Status status={r.status} />} />
      <div className="detail-grid">
        <div className="detail-main">
          <div className="hero-amount">
            <div>
              <p className="section-kicker">Amount to recover</p>
              <div className="amount">{formatINR(r.amount)}</div>
              <p className="text-sm text-muted-foreground">{r.payment}</p>
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
                <span>{r.probability}%</span>
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
                <h3>{r.reason}</h3>
                <p>
                  The payment attempt was declined, but the customer has a strong history of successful payments. A low-friction
                  reminder is the best next step.
                </p>
              </div>
            </div>
            <div className="action-row">
              <button className="button-primary">
                <Sparkles className="size-4" />
                Send reminder
              </button>
              <button className="button-secondary">Mark as resolved</button>
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>Recovery timeline</h2>
              <span className="text-sm text-muted-foreground">Today</span>
            </div>
            <div className="timeline">
              <div>
                <span className="timeline-dot done">
                  <Check className="size-3" />
                </span>
                <div>
                  <b>Payment failed</b>
                  <p>Today at 10:42 AM · {r.reason}</p>
                </div>
              </div>
              <div>
                <span className="timeline-dot done">
                  <Check className="size-3" />
                </span>
                <div>
                  <b>Case created</b>
                  <p>Today at 10:43 AM · Automatically added to queue</p>
                </div>
              </div>
              <div>
                <span className="timeline-dot current" />
                <div>
                  <b>Recommended action</b>
                  <p>Send a gentle reminder via email</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        <aside className="detail-side">
          <div className="panel">
            <p className="section-kicker">Customer</p>
            <div className="customer-profile">
              <div className="avatar large">{r.customer.split(' ').map((x) => x[0]).join('')}</div>
              <div>
                <h3>{r.customer}</h3>
                <p>{r.email}</p>
              </div>
            </div>
            <div className="side-row">
              <span>Lifetime value</span>
              <b>{formatINR(18400)}</b>
            </div>
            <div className="side-row">
              <span>Previous recoveries</span>
              <b>4</b>
            </div>
          </div>
          <div className="panel">
            <p className="section-kicker">Message preview</p>
            <div className="message-preview">
              <p>Hi {r.customer.split(' ')[0]},</p>
              <p>
                We noticed a payment didn&apos;t go through. No worries — you can update your payment method in just a moment.
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
  return (
    <>
      <PageIntro title="Analytics" subtitle="Understand what is driving recovery performance." />
      <div className="metric-grid">
        <Metric label="Avg. time to recover" value="2.4 days" change="16.0%" note="Faster than last month" />
        <Metric label="Best performing channel" value="Email" change="8.2%" note="68.2% conversion" />
        <Metric label="Messages sent" value="1,842" change="21.4%" note="This month" />
        <Metric label="Customer satisfaction" value="94.8%" change="2.1%" note="After recovery" />
      </div>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Recovery trend</p>
            <h2>Cases recovered over time</h2>
          </div>
          <select className="select">
            <option>Monthly</option>
            <option>Weekly</option>
          </select>
        </div>
        <MiniChart />
      </div>
    </>
  )
}

function Customers() {
  return (
    <>
      <PageIntro title="Customers" subtitle="A clear view of customers with payment activity." />
      <div className="table-card">
        <div className="table-heading">
          <div className="search">
            <Search className="size-4 text-muted-foreground" />
            <input placeholder="Search customers..." />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Lifetime value</th>
                <th>Open cases</th>
                <th>Last payment</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.email}>
                  <td>
                    <Link href={`/customers/${c.id}`} className="customer-link">
                      <div className="avatar small">{c.name.split(' ').map((x) => x[0]).join('')}</div>
                      <span>
                        <b>{c.name}</b>
                        <small>{c.email}</small>
                      </span>
                    </Link>
                  </td>
                  <td>{formatINR(c.lifetime)}</td>
                  <td>{c.cases}</td>
                  <td className="text-muted-foreground">{c.lastPayment}</td>
                  <td>
                    <Link href={`/customers/${c.id}`} className="icon-btn" aria-label="View customer">
                      <ChevronRight className="size-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function CustomerDetail({ id }: { id: string }) {
  const c = getCustomer(id)
  const customerPayments = getCustomerPayments(c.id)
  const customerRecoveries = getCustomerRecoveries(c.id)
  const events = getCustomerTimeline(c.id)

  return (
    <>
      <Link href="/customers" className="back-link">
        ← Back to customers
      </Link>
      <PageIntro
        title={c.name}
        subtitle={`${c.company} · Customer since ${c.joined}`}
        action={<button className="button-secondary">Edit profile</button>}
      />
      <div className="metric-grid">
        <Metric label="Lifetime value" value={formatINR(c.lifetime)} change="12.4%" note={`${c.segment} segment`} />
        <Metric label="Recovery rate" value={`${c.recoveryRate}%`} change="8.2%" note="Customer success score" />
        <Metric label="Open recoveries" value={c.cases.toString()} change="1" note="Needs attention" positive={false} />
        <Metric label="Last payment" value={c.lastPayment} change="On time" note="Payment activity" />
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
                {customerPayments.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <b>{p.id}</b>
                    </td>
                    <td>{formatINR(p.amount)}</td>
                    <td className="text-muted-foreground">{p.method}</td>
                    <td>
                      <span className={`status ${p.status === 'Succeeded' ? 'status-good' : 'status-warn'}`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="text-muted-foreground">{p.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Activity</p>
              <h2>Customer timeline</h2>
            </div>
          </div>
          <div className="timeline">
            {events.map((e, i) => (
              <div key={`${e.label}-${i}`}>
                <span className={`timeline-dot ${e.kind === 'success' ? 'done' : 'current'}`} />
                <div>
                  <b>{e.label}</b>
                  <p>
                    {e.date} · {e.detail}
                  </p>
                </div>
              </div>
            ))}
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
                <th />
              </tr>
            </thead>
            <tbody>
              {customerRecoveries.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/recoveries/${r.id}`} className="customer-link">
                      <b>{r.id}</b>
                    </Link>
                  </td>
                  <td>{formatINR(r.amount)}</td>
                  <td>
                    <Status status={r.status} />
                  </td>
                  <td className="text-muted-foreground">{r.reason}</td>
                  <td>
                    <Link href={`/recoveries/${r.id}`} className="icon-btn" aria-label="View case">
                      <ChevronRight className="size-4" />
                    </Link>
                  </td>
                </tr>
              ))}
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

  // Local state abstractions for UI demo actions
  const [recoveriesList, setRecoveriesList] = useState<Recovery[]>(initialRecoveries)
  const [policiesList, setPoliciesList] = useState<Policy[]>(initialPolicies)
  const [notifsList, setNotifsList] = useState<Notification[]>(initialNotifications)
  const [settingsState, setSettingsState] = useState<WorkspaceSettings>(initialSettings)

  // Modals state
  const [recoveryModalOpen, setRecoveryModalOpen] = useState(false)
  const [policyModalOpen, setPolicyModalOpen] = useState(false)
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null)
  const [settingsModalKind, setSettingsModalKind] = useState<'workspace' | 'notifications' | 'account' | null>(null)

  useEffect(() => {
    const savedTheme = window.localStorage.getItem('payback-theme')
    if (savedTheme) setDark(savedTheme === 'dark')
    const session = getDemoSession()
    if (!session) router.replace('/sign-in')
    setReady(true)
  }, [router])

  useEffect(() => {
    if (ready) {
      window.localStorage.setItem('payback-theme', dark ? 'dark' : 'light')
    }
  }, [dark, ready])

  if (!ready || !getDemoSession()) return null

  function handleCreateRecovery(rec: Omit<Recovery, 'id' | 'created' | 'probability' | 'nextAction'>) {
    const newRec = addRecovery(rec)
    setRecoveriesList([...initialRecoveries])
  }

  function handleSavePolicy(pol: Omit<Policy, 'id'>, existingId?: string) {
    if (existingId) {
      updatePolicy(existingId, pol)
    } else {
      addPolicy(pol)
    }
    setPoliciesList([...initialPolicies])
  }

  function handleMarkNotifRead(notifId: string) {
    markNotificationRead(notifId)
    setNotifsList([...initialNotifications])
  }

  function handleMarkAllNotifsRead() {
    markAllNotificationsRead()
    setNotifsList([...initialNotifications])
  }

  function handleUpdateSettings(updates: Partial<WorkspaceSettings>) {
    const updated = updateWorkspaceSettings(updates)
    setSettingsState({ ...updated })
  }

  let content: React.ReactNode
  if (view === 'recoveries') {
    content = <Recoveries recoveriesList={recoveriesList} onNewRecovery={() => setRecoveryModalOpen(true)} />
  } else if (view === 'detail') {
    content = <Detail id={id ?? 'RCV-2048'} />
  } else if (view === 'analytics') {
    content = <Analytics />
  } else if (view === 'customers') {
    content = <Customers />
  } else if (view === 'customer-detail') {
    content = <CustomerDetail id={id ?? 'cus_maya'} />
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
    content = <Dashboard onNewRecovery={() => setRecoveryModalOpen(true)} />
  }

  return (
    <div className={`app ${dark ? 'theme-dark' : 'theme-light'}`}>
      <Sidebar
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        mobile={mobile}
        onNavigate={() => setMobile(false)}
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
        />
        <div className="content">{content}</div>
      </main>

      {/* Dialog Modals */}
      <NewRecoveryDialog
        open={recoveryModalOpen}
        onClose={() => setRecoveryModalOpen(false)}
        onCreate={handleCreateRecovery}
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
  return (
    <main className="landing">
      <div className="landing-grid-bg" aria-hidden="true" />
      
      <nav className="landing-nav">
        <Logo />
        <div className="flex items-center gap-3">
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
              <p className="section-kicker">Overview</p>
              <h3>Good morning, Aditi</h3>
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

      {/* Feature capabilities grid */}
      <section className="landing-features">
        <div className="feature-card">
          <div className="feature-icon">
            <Activity className="size-5" />
          </div>
          <h3>Intelligent Retries</h3>
          <p>Machine-learned recovery probability engine determines optimal retry timing per customer history and payment channel.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">
            <Sparkles className="size-5" />
          </div>
          <h3>Gentle Multi-Channel Messaging</h3>
          <p>Deliver personalized, low-friction recovery links through WhatsApp and Email without spamming or damaging loyalty.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">
            <ShieldCheck className="size-5" />
          </div>
          <h3>Human-in-the-Loop Policies</h3>
          <p>Customizable merchant guardrails with automatic escalation for high-value transactions and sensitive accounts.</p>
        </div>
      </section>
    </main>
  )
}


