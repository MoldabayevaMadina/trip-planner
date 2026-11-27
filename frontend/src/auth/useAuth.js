import { useContext } from 'react'
import { AuthContext } from './AuthContext'

/** const { user, login, logout } = useAuth() — in any component inside <AuthProvider> */
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}