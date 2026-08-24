import { createContext, useContext, useMemo, useState } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('ticket_user') || 'null'))
  const save = (data) => {
    localStorage.setItem('ticket_token', data.access_token)
    localStorage.setItem('ticket_user', JSON.stringify(data.user))
    setUser(data.user)
  }
  const login = async (values) => save((await api.post('/api/auth/login', values)).data)
  const register = async (values) => save((await api.post('/api/auth/register', values)).data)
  const logout = () => {
    localStorage.removeItem('ticket_token')
    localStorage.removeItem('ticket_user')
    setUser(null)
  }
  const value = useMemo(() => ({ user, login, register, logout }), [user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)

