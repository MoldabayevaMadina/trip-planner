import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

/**
 * Wraps the routes that need a logged-in user.
 * Guest → /login, and the page they wanted is remembered in `state.from` to come back after login.
 */
export default function ProtectedRoute() {
  const { user, checking } = useAuth()
  const location = useLocation()

  if (checking) return <p className="muted">Checking your session…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />          // the protected page itself
}