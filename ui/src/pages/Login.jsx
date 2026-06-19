import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { AUTH_ENABLED } from '../auth/config'
import './Login.css'

export default function Login() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/chat'

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  // If already logged in, go to the intended page (or chat)
  if (isAuthenticated) {
    navigate(from, { replace: true })
    return null
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      if (err.message === 'PASSWORD_RESET_REQUIRED') {
        setError('A password reset is required. Please contact your administrator.')
      } else if (err.code === 'NotAuthorizedException') {
        setError('Incorrect email or password.')
      } else if (err.code === 'UserNotFoundException') {
        setError('No account found for that email.')
      } else if (err.code === 'UserNotConfirmedException') {
        setError('Account not confirmed. Please contact your administrator.')
      } else {
        setError(err.message || 'Sign in failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <Link to="/" className="login-logo">William</Link>
        <h1 className="login-title">Sign in</h1>
        <p className="login-sub">
          {AUTH_ENABLED
            ? 'Use your team credentials to access William.'
            : 'Auth is not configured — running in dev mode.'}
        </p>

        {!AUTH_ENABLED && (
          <div className="login-dev-notice">
            Set <code>VITE_COGNITO_USER_POOL_ID</code> and{' '}
            <code>VITE_COGNITO_CLIENT_ID</code> in <code>ui/.env.local</code> to
            enable Cognito authentication.
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit}>
          {error && <div className="login-error">{error}</div>}

          <div className="login-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              disabled={!AUTH_ENABLED}
            />
          </div>

          <div className="login-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              disabled={!AUTH_ENABLED}
            />
          </div>

          <button
            type="submit"
            className="login-btn"
            disabled={loading || !AUTH_ENABLED}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="login-footer">
          <Link to="/">← Back to Home</Link>
        </div>
      </div>
    </div>
  )
}
