'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { register } from '@/lib/api/auth'

export default function SignUpPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const data = new FormData(e.currentTarget)
    const name = String(data.get('name') || '').trim()
    const email = String(data.get('email') || '').trim()
    const password = String(data.get('password') || '').trim()

    try {
      await register(name, email, undefined, password)
      router.push('/sign-in?registered=true')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.')
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <Link href="/" className="auth-logo">
          PayBack
        </Link>
        <h1>Create your workspace</h1>
        <p>Start recovering more revenue with less effort.</p>

        {error && (
          <div style={{ padding: '10px 14px', borderRadius: '8px', marginBottom: '14px', background: 'var(--status-bad-bg)', color: 'var(--status-bad-text)', fontSize: '12px' }}>
            {error}
          </div>
        )}

        <form onSubmit={submit}>
          <label>
            Full name
            <input name="name" required type="text" placeholder="e.g. Rahul Sharma" />
          </label>
          <label>
            Work email
            <input name="email" required type="email" placeholder="you@company.com" />
          </label>
          <label>
            Password
            <input name="password" required minLength={8} type="password" placeholder="At least 8 characters" />
          </label>
          <button className="button-primary" type="submit" disabled={loading}>
            {loading ? 'Creating workspace…' : 'Create account'}
          </button>
        </form>

        <div className="auth-switch">
          Already have an account? <Link href="/sign-in">Sign in</Link>
        </div>
      </div>
    </main>
  )
}

