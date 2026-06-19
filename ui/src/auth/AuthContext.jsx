import { createContext, useContext, useEffect, useState } from 'react'
import { getCurrentUser, signIn as cognitoSignIn, signOut as cognitoSignOut, getIdToken } from './cognito'
import { AUTH_ENABLED } from './config'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)   // { email, sub } or null
  const [token, setToken]     = useState(null)   // idToken string
  const [loading, setLoading] = useState(true)   // checking session on mount

  // Restore session on page load
  useEffect(() => {
    if (!AUTH_ENABLED) {
      setLoading(false)
      return
    }
    Promise.all([getCurrentUser(), getIdToken()])
      .then(([u, t]) => { setUser(u); setToken(t) })
      .finally(() => setLoading(false))
  }, [])

  async function login(email, password) {
    const result = await cognitoSignIn(email, password)
    setUser(result.user)
    setToken(result.idToken)
    return result
  }

  function logout() {
    cognitoSignOut()
    setUser(null)
    setToken(null)
  }

  const isAuthenticated = AUTH_ENABLED ? Boolean(user && token) : true

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, isAuthenticated, AUTH_ENABLED }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
