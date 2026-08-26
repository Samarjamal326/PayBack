export type RecoveryStatus = 'Recovered' | 'In review' | 'Failed'
export type PaymentStatus = 'Succeeded' | 'Failed' | 'Pending'
export type TimelineEvent = { label: string; detail: string; date: string; kind: 'success' | 'warning' | 'neutral' }
export type Payment = { id: string; customerId: string; amount: number; status: PaymentStatus; method: string; date: string }
export type Recovery = { id: string; customerId: string; customer: string; email: string; amount: number; status: RecoveryStatus; reason: string; created: string; payment: string; probability: number; nextAction: string }
export type Customer = { id: string; name: string; email: string; company: string; lifetime: number; cases: number; lastPayment: string; joined: string; segment: string; recoveryRate: number }

export const customers: Customer[] = [
  { id: 'cus_maya', name: 'Maya Shah', email: 'maya.shah@example.com', company: 'Luma Labs', lifetime: 18400, cases: 2, lastPayment: 'Today', joined: 'Jan 12, 2024', segment: 'Growth', recoveryRate: 82 },
  { id: 'cus_arjun', name: 'Arjun Mehta', email: 'arjun.mehta@example.com', company: 'Northstar', lifetime: 7200, cases: 1, lastPayment: 'Today', joined: 'Mar 04, 2024', segment: 'Starter', recoveryRate: 100 },
  { id: 'cus_noah', name: 'Noah Williams', email: 'noah.w@example.com', company: 'Orbit Commerce', lifetime: 32800, cases: 4, lastPayment: 'Yesterday', joined: 'Nov 18, 2023', segment: 'Enterprise', recoveryRate: 76 },
  { id: 'cus_ishita', name: 'Ishita Rao', email: 'ishita.rao@example.com', company: 'Vela Studio', lifetime: 9600, cases: 1, lastPayment: 'Aug 23', joined: 'Jun 21, 2024', segment: 'Growth', recoveryRate: 61 },
]
export const recoveries: Recovery[] = [
  { id: 'RCV-2048', customerId: 'cus_maya', customer: 'Maya Shah', email: 'maya.shah@example.com', amount: 2499, status: 'In review', reason: 'Insufficient funds', created: 'Today, 10:42 AM', payment: 'UPI ·•• 4821', probability: 78, nextAction: 'Send a gentle reminder' },
  { id: 'RCV-2047', customerId: 'cus_arjun', customer: 'Arjun Mehta', email: 'arjun.mehta@example.com', amount: 899, status: 'Recovered', reason: 'Card expired', created: 'Today, 9:18 AM', payment: 'Visa ·•• 1092', probability: 100, nextAction: 'No action needed' },
  { id: 'RCV-2046', customerId: 'cus_noah', customer: 'Noah Williams', email: 'noah.w@example.com', amount: 1499, status: 'In review', reason: 'Bank declined', created: 'Yesterday, 4:36 PM', payment: 'Mastercard ·•• 7204', probability: 64, nextAction: 'Try alternate channel' },
  { id: 'RCV-2045', customerId: 'cus_ishita', customer: 'Ishita Rao', email: 'ishita.rao@example.com', amount: 4999, status: 'Failed', reason: 'Payment timed out', created: 'Yesterday, 2:09 PM', payment: 'UPI ·•• 9018', probability: 32, nextAction: 'Escalate to support' },
  { id: 'RCV-2044', customerId: 'cus_noah', customer: 'Noah Williams', email: 'noah.w@example.com', amount: 799, status: 'Recovered', reason: 'Insufficient funds', created: 'Aug 23, 11:52 AM', payment: 'Amex ·•• 1822', probability: 100, nextAction: 'No action needed' },
]
export const payments: Payment[] = [
  { id: 'PAY-7781', customerId: 'cus_maya', amount: 2499, status: 'Failed', method: 'UPI ·•• 4821', date: 'Today, 10:42 AM' },
  { id: 'PAY-7644', customerId: 'cus_maya', amount: 2499, status: 'Succeeded', method: 'UPI ·•• 4821', date: 'Jul 26, 2024' },
  { id: 'PAY-7402', customerId: 'cus_maya', amount: 1999, status: 'Succeeded', method: 'Visa ·•• 1180', date: 'Jun 26, 2024' },
  { id: 'PAY-7028', customerId: 'cus_noah', amount: 1499, status: 'Failed', method: 'Mastercard ·•• 7204', date: 'Yesterday, 4:36 PM' },
]
export const timelines: Record<string, TimelineEvent[]> = {
  cus_maya: [{ label: 'Payment failed', detail: 'Insufficient funds · PAY-7781', date: 'Today, 10:42 AM', kind: 'warning' }, { label: 'Recovery case created', detail: 'Added to queue automatically', date: 'Today, 10:43 AM', kind: 'neutral' }, { label: 'Reminder scheduled', detail: 'Email recommended by policy engine', date: 'Today, 10:44 AM', kind: 'success' }],
  cus_arjun: [{ label: 'Payment recovered', detail: 'Card updated successfully', date: 'Today, 9:18 AM', kind: 'success' }, { label: 'Recovery closed', detail: 'No further action needed', date: 'Today, 9:19 AM', kind: 'neutral' }],
  cus_noah: [{ label: 'Payment failed', detail: 'Bank declined · PAY-7028', date: 'Yesterday, 4:36 PM', kind: 'warning' }, { label: 'Alternate channel suggested', detail: 'WhatsApp has the strongest conversion', date: 'Yesterday, 4:38 PM', kind: 'success' }],
  cus_ishita: [{ label: 'Payment timed out', detail: 'UPI ·•• 9018', date: 'Yesterday, 2:09 PM', kind: 'warning' }, { label: 'Case escalated', detail: 'Support review required', date: 'Yesterday, 2:10 PM', kind: 'neutral' }],
}
export const metrics = { recovered: 184200, recoveryRate: 68.4, atRisk: 42800, activeCases: 126 }
export const chartData = [42, 58, 49, 68, 55, 72, 69, 81, 74, 88, 84, 92]
export type NotificationType = 'recovery_completed' | 'recovery_escalated' | 'action_failed' | 'payment_recovered' | 'webhook_issue'
export type Notification = {
  id: string
  type: NotificationType
  title: string
  message: string
  time: string
  read: boolean
}

export type Policy = {
  id: string
  name: string
  description: string
  status: 'Active' | 'Draft'
  maxRetries: number
  maxMessages: number
  recoveryWindowHours: number
  highValueThreshold: number
  humanApprovalRequired: boolean
}

export type WorkspaceSettings = {
  workspaceName: string
  timezone: string
  notifyRecoveryCompleted: boolean
  notifyRecoveryEscalated: boolean
  notifyActionFailed: boolean
  notifyPaymentRecovered: boolean
}

export let notifications: Notification[] = [
  { id: 'notif_1', type: 'payment_recovered', title: 'Payment Recovered', message: 'Arjun Mehta completed recovery for ₹899 via Visa ·•• 1092', time: '10m ago', read: false },
  { id: 'notif_2', type: 'recovery_escalated', title: 'High-Value Escalation', message: 'Case RCV-2045 for Ishita Rao (₹4,999) requires support review', time: '1h ago', read: false },
  { id: 'notif_3', type: 'recovery_completed', title: 'Recovery Completed', message: 'Case RCV-2044 for Noah Williams (₹799) closed successfully', time: '3h ago', read: true },
  { id: 'notif_4', type: 'action_failed', title: 'WhatsApp Dispatch Retry', message: 'WhatsApp reminder for Maya Shah queued for retry', time: 'Yesterday', read: true },
]

export let policies: Policy[] = [
  {
    id: 'pol_1',
    name: 'Smart Retry & Recovery Policy',
    description: 'Automatically retries payments and sequences gentle reminders based on ML recovery likelihood.',
    status: 'Active',
    maxRetries: 3,
    maxMessages: 2,
    recoveryWindowHours: 72,
    highValueThreshold: 10000,
    humanApprovalRequired: false,
  },
  {
    id: 'pol_2',
    name: 'High-Value Escalation Guardrail',
    description: 'Routes high-risk or large transactions directly to merchant review to protect customer relationships.',
    status: 'Active',
    maxRetries: 1,
    maxMessages: 1,
    recoveryWindowHours: 24,
    highValueThreshold: 5000,
    humanApprovalRequired: true,
  },
  {
    id: 'pol_3',
    name: 'Subscription Grace Period Policy',
    description: 'Extends a 7-day payment update window before pausing customer subscription access.',
    status: 'Draft',
    maxRetries: 5,
    maxMessages: 3,
    recoveryWindowHours: 168,
    highValueThreshold: 25000,
    humanApprovalRequired: false,
  },
]

export let workspaceSettings: WorkspaceSettings = {
  workspaceName: 'Acme Commerce',
  timezone: 'Asia/Kolkata (IST)',
  notifyRecoveryCompleted: true,
  notifyRecoveryEscalated: true,
  notifyActionFailed: true,
  notifyPaymentRecovered: true,
}

export function formatINR(value: number) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value) }
export function getRecovery(id: string) { return recoveries.find((r) => r.id === id) ?? recoveries[0] }
export function getCustomer(id: string) { return customers.find((c) => c.id === id) ?? customers[0] }
export function getCustomerPayments(id: string) { return payments.filter((p) => p.customerId === id) }
export function getCustomerRecoveries(id: string) { return recoveries.filter((r) => r.customerId === id) }
export function getCustomerTimeline(id: string) { return timelines[id] ?? [] }
export function getCustomerByEmail(email: string) { return customers.find((c) => c.email === email) }

export function addRecovery(recovery: Omit<Recovery, 'id' | 'created' | 'probability' | 'nextAction'>): Recovery {
  const newId = `RCV-${2049 + recoveries.length}`
  const newRec: Recovery = {
    ...recovery,
    id: newId,
    created: 'Just now',
    probability: Math.floor(Math.random() * 30) + 65,
    nextAction: 'Send a gentle reminder',
  }
  recoveries.unshift(newRec)
  return newRec
}

export function addPolicy(policy: Omit<Policy, 'id'>): Policy {
  const newPol: Policy = {
    ...policy,
    id: `pol_${Date.now()}`,
  }
  policies.unshift(newPol)
  return newPol
}

export function updatePolicy(id: string, updates: Partial<Policy>): Policy | null {
  const idx = policies.findIndex((p) => p.id === id)
  if (idx === -1) return null
  policies[idx] = { ...policies[idx], ...updates }
  return policies[idx]
}

export function markNotificationRead(id: string) {
  const n = notifications.find((x) => x.id === id)
  if (n) n.read = true
}

export function markAllNotificationsRead() {
  notifications.forEach((n) => { n.read = true })
}

export function updateWorkspaceSettings(updates: Partial<WorkspaceSettings>) {
  workspaceSettings = { ...workspaceSettings, ...updates }
  return workspaceSettings
}


