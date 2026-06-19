import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="auth-loading">
        <span className="dots"><span /><span /><span /></span>
      </div>
    )
  }

  if (!isAuthenticated) {
    // Save the page they were trying to reach — Login will redirect back after sign-in
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
