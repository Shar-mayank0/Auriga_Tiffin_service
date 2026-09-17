import { createContext, useContext, useEffect, useState } from 'react'
import * as authApi from '../api/auth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(() => localStorage.getItem('access'))
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('user') || 'null'))
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (accessToken) localStorage.setItem('access', accessToken)
  }, [accessToken])

  const login = async (credentials) => {
    setLoading(true)
    try {
      const { data } = await authApi.login(credentials)
      setAccessToken(data.access)
      localStorage.setItem('refresh', data.refresh)
      return data
    } finally {
      setLoading(false)
    }
  }

  const register = async (formData) => {
    setLoading(true)
    try {
      const { data } = await authApi.register(formData)
      setAccessToken(data.access)
      localStorage.setItem('refresh', data.refresh)
      return data
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    const refresh = localStorage.getItem('refresh')
    try {
      if (refresh) await authApi.logout(refresh)
    } catch {
      // The local session still needs to be cleared if the token is expired.
    }
    setAccessToken(null)
    setUser(null)
    localStorage.removeItem('access')
    localStorage.removeItem('refresh')
    localStorage.removeItem('user')
  }

  return (
    <AuthContext.Provider value={{ accessToken, user, setUser, loading, isAuthenticated: Boolean(accessToken), login, logout, register }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)