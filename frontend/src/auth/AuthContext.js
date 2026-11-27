import { createContext } from 'react'

/** { user, checking, login, register, logout, setUser } — filled by <AuthProvider> */
export const AuthContext = createContext(null)