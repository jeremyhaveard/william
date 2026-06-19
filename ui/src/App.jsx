import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Home     from './pages/Home'
import Contact  from './pages/Contact'
import Login    from './pages/Login'
import ChatPage from './pages/ChatPage'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/"        element={<Home />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/login"   element={<Login />} />
        <Route path="/chat"    element={
          <ProtectedRoute><ChatPage /></ProtectedRoute>
        } />
      </Routes>
    </AuthProvider>
  )
}
