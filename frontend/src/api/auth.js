import client from './client.js'

export const register = (data) => client.post('/auth/register/', data)
export const login = (credentials) => client.post('/auth/login/', credentials)
export const logout = (refresh) => client.post('/auth/logout/', { refresh })
export const refreshToken = (refresh) => client.post('/auth/token/refresh/', { refresh })
