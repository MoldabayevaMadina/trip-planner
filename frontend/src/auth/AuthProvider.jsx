import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { AuthContext } from './AuthContext'
import { clearTokens, getAccessToken, setTokens } from './tokens'

/** Keeps the current user for the whole app and gives login / register / logout. */
export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // a token is saved from the last visit: check whose it is before showing protected pages
  const [checking, setChecking] = useState(() => Boolean(getAccessToken()))

  useEffect(() => {
    if (!getAccessToken()) return
    api('/auth/me/')
      .then(setUser)
      .catch(() => {
        clearTokens()
        setUser(null)
      })
      .finally(() => setChecking(false))
  }, [])

  // api() fires this event when even the refresh token is no longer valid
  useEffect(() => {
    const onLogout = () => setUser(null)
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const login = useCallback(async (username, password) => {
    const tokens = await api('/auth/login/', { method: 'POST', body: { username, password }, auth: false })
    setTokens(tokens)                    // { access, refresh }
    const me = await api('/auth/me/')
    setUser(me)
    return me
  }, [])

  const register = useCallback(async ({ username, email, password }) => {
    const data = await api('/auth/register/', {
      method: 'POST', body: { username, email, password }, auth: false,
    })
    setTokens({ access: data.access, refresh: data.refresh })
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, setUser, checking, login, register, logout }),
    [user, checking, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}