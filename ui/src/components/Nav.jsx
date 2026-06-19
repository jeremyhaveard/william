import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import './Nav.css'

export default function Nav() {
  const { isAuthenticated, user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <nav className="nav">
      <NavLink to="/" className="nav-logo">William</NavLink>
      <div className="nav-links">
        <NavLink to="/"        className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} end>Home</NavLink>
        <NavLink to="/contact" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Contact</NavLink>
      </div>
      <div className="nav-right">
        {isAuthenticated && user ? (
          <>
            <span className="nav-user">{user.email}</span>
            <NavLink to="/chat" className="nav-btn primary">Open William</NavLink>
            <button className="nav-btn ghost" onClick={handleLogout}>Sign Out</button>
          </>
        ) : (
          <NavLink to="/login" className="nav-btn primary">Sign In</NavLink>
        )}
      </div>
    </nav>
  )
}
