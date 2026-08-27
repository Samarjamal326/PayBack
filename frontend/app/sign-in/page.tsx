'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { FormEvent, Suspense, useState } from 'react'
import { login } from '@/lib/api/auth'

function SignInForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const justRegistered = searchParams.get('registered') === 'true'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const data = new FormData(e.currentTarget)
    const email = String(data.get('email') || '').trim()
    const password = String(data.get('password') || '').trim()

    try {
      await login(email, password)
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed. Please check your credentials.')
      setLoading(false)
    }
  }

  async function handleDemoLogin() {
    setError(null)
    setLoading(true)
    try {
      await login('admin@payback.io', 'demo-password')
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Demo sign in failed.')
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <Link href="/" className="auth-logo">
          PayBack
        </Link>
        <h1>Welcome back</h1>
        <p>Sign in to your recovery workspace.</p>

        {justRegistered && (
          <div style={{ padding: '10px 14px', borderRadius: '8px', marginBottom: '14px', background: 'var(--status-good-bg)', color: 'var(--status-good-text)', fontSize: '12px' }}>
            Account created successfully! Please sign in with your credentials.
          </div>
        )}

        {error && (
          <div style={{ padding: '10px 14px', borderRadius: '8px', marginBottom: '14px', background: 'var(--status-bad-bg)', color: 'var(--status-bad-text)', fontSize: '12px' }}>
            {error}
          </div>
        )}

        <form onSubmit={submit}>
          <label>
            Email
            <input name="email" type="email" required placeholder="you@company.com" />
          </label>
          <label>
            Password
            <input name="password" type="password" required placeholder="••••••••" />
          </label>
          <div className="auth-options">
            <label className="check">
              <input type="checkbox" defaultChecked /> Remember me
            </label>
            <a href="#forgot">Forgot password?</a>
          </div>
          <button className="button-primary" type="submit" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <button className="button-secondary demo-button" type="button" onClick={handleDemoLogin} disabled={loading}>
          Use demo account
        </button>
        <p className="demo-hint">admin@payback.io · Pre-loaded demo data</p>

        <div className="auth-switch">
          New to PayBack? <Link href="/sign-up">Create an account</Link>
        </div>
      </div>
    </main>
  )
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="auth-page"><div className="auth-card"><p>Loading…</p></div></div>}>
      <SignInForm />
    </Suspense>
  )
}

