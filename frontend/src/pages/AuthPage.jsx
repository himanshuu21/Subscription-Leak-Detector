import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'

function GoogleIcon() {
  return <svg className="google-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.07H12v3.92h5.38a4.6 4.6 0 0 1-2 3.02v2.54h3.24c1.9-1.75 2.98-4.33 2.98-7.41Z"/><path fill="#34A853" d="M12 22c2.7 0 4.98-.9 6.64-2.43l-3.24-2.54c-.9.6-2.05.96-3.4.96-2.61 0-4.82-1.76-5.61-4.13H3.04v2.62A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.39 13.86A6.01 6.01 0 0 1 6.07 12c0-.65.11-1.28.32-1.86V7.52H3.04A10 10 0 0 0 2 12c0 1.61.39 3.14 1.04 4.48l3.35-2.62Z"/><path fill="#EA4335" d="M12 6.01c1.47 0 2.79.51 3.83 1.5l2.88-2.88A9.65 9.65 0 0 0 12 2a10 10 0 0 0-8.96 5.52l3.35 2.62C7.18 7.77 9.39 6.01 12 6.01Z"/></svg>
}

export default function AuthPage({ config, onAuthenticated }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const signingUp = mode === 'signup'
  const oauthError = useMemo(() => {
    const code = searchParams.get('oauth_error')
    if (!code) return ''
    if (code === 'unverified') return 'Google did not provide a verified email address.'
    if (code === 'conflict') return 'This email is already connected to another Google account.'
    return 'Google sign-in could not be completed. Please try again.'
  }, [searchParams])

  async function submit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await api.authenticate(mode, { email: email.trim(), password })
      onAuthenticated()
      navigate(signingUp ? '/upload-page' : '/dashboard')
    } catch (err) {
      setError(err.message || 'Network error. Please try again.')
    } finally { setSubmitting(false) }
  }

  function toggleMode() {
    setMode(signingUp ? 'login' : 'signup')
    setEmail('')
    setPassword('')
    setError('')
  }

  return <section className="auth-page">
    <div className="auth-intro">
      <span className="eyebrow">Take back control</span>
      <h1>{signingUp ? 'Make every subscription count.' : 'Your money should never disappear quietly.'}</h1>
      <p>Find recurring payments, spot price hikes, and see exactly what you could save—all from one simple transaction upload.</p>
      <div className="feature-row">
        <span>✓ Private by design</span><span>✓ Clear confidence scores</span><span>✓ No bank connection needed</span>
      </div>
    </div>
    <div className="auth-card" id="auth-form">
      <div className="auth-card-heading">
        <h2>{signingUp ? 'Create your account' : 'Welcome back'}</h2>
        <p>{signingUp ? 'Start finding hidden subscriptions.' : 'Sign in to review your recurring spend.'}</p>
      </div>
      {config.google_oauth_enabled && <>
        <a href="/api/auth/google/login" className="google-button"><GoogleIcon/> Continue with Google</a>
        <div className="divider"><span>or continue with email</span></div>
      </>}
      <form onSubmit={submit}>
        <label>Email address<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required /></label>
        <label>Password<input type="password" autoComplete={signingUp ? 'new-password' : 'current-password'} minLength={signingUp ? 12 : 1} maxLength="128" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={signingUp ? 'At least 12 characters' : 'Enter your password'} required /></label>
        {signingUp && <p className="field-hint">Use at least 12 characters.</p>}
        {(error || oauthError) && <div className="alert error" role="alert">{error || oauthError}</div>}
        <button className="primary-button full" disabled={submitting}>{submitting ? 'Please wait…' : signingUp ? 'Create account' : 'Sign in'}</button>
      </form>
      <p className="auth-switch">{signingUp ? 'Already have an account?' : 'Don’t have an account?'} <button type="button" onClick={toggleMode}>{signingUp ? 'Sign in' : 'Sign up'}</button></p>
    </div>
  </section>
}
