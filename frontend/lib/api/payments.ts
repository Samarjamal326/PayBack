// API service for payment operations
import { getAuthSession } from '@/lib/auth-session'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface CreatePaymentRequest {
  customer_id: string
  amount: number
  currency?: string
  description?: string
}

export interface CreatePaymentWithCustomerRequest {
  customer_name: string
  customer_email: string
  customer_phone: string
  amount: number
  currency?: string
  payment_method?: string
}

export interface CreatePaymentResponse {
  transaction_id: string
  razorpay_order_id?: string
  payment_link_url?: string
  amount: number
  currency: string
  status: string
  customer_name: string
  created_at: string
}

export interface Transaction {
  id: string
  merchant_id?: string
  customer_id: string
  amount: number
  currency: string
  payment_method: string
  status: string
  failure_reason?: string
  failure_code?: string
  razorpay_order_id?: string
  razorpay_payment_id?: string
  created_at: string
  updated_at: string
}

async function getAuthHeaders(): Promise<HeadersInit> {
  const session = getAuthSession()
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`
  }
  
  return headers
}

export async function createPayment(request: CreatePaymentRequest): Promise<CreatePaymentResponse> {
  const headers = await getAuthHeaders()
  
  const response = await fetch(`${API_BASE}/api/v1/payments/create`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to create payment')
  }
  
  return response.json()
}

export async function createPaymentWithCustomer(request: CreatePaymentWithCustomerRequest): Promise<CreatePaymentResponse> {
  const headers = await getAuthHeaders()
  
  const response = await fetch(`${API_BASE}/api/v1/payments/create-with-customer`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to create payment')
  }
  
  return response.json()
}

export async function getTransaction(transactionId: string): Promise<Transaction> {
  const headers = await getAuthHeaders()
  
  const response = await fetch(`${API_BASE}/api/v1/payments/transaction/${transactionId}`, {
    method: 'GET',
    headers,
  })
  
  if (!response.ok) {
    throw new Error('Failed to fetch transaction')
  }
  
  return response.json()
}

export async function getCustomerPayments(customerId: string): Promise<Transaction[]> {
  const headers = await getAuthHeaders()
  
  const response = await fetch(`${API_BASE}/api/v1/payments/customer/${customerId}`, {
    method: 'GET',
    headers,
  })
  
  if (!response.ok) {
    throw new Error('Failed to fetch customer payments')
  }
  
  return response.json()
}
