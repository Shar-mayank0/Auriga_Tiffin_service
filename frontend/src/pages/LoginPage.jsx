import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function LoginPage() {
  const { register, handleSubmit, formState: { errors } } = useForm()
  const { login, loading, isAuthenticated } = useAuth()
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  const onSubmit = async ({ identifier, password }) => {
    setError('')
    try {
      await login({ username: identifier, password })
      navigate(location.state?.from?.pathname || '/dashboard', { replace: true })
    } catch (requestError) {
      setError(Object.values(requestError.response?.data || {}).flat().join(' ') || 'Unable to log in.')
    }
  }
  return <AuthForm title="Welcome back" submit="Log in" loading={loading} onSubmit={onSubmit} register={register} handleSubmit={handleSubmit} errors={errors} apiError={error} />
}

function AuthForm({ title, submit, loading, onSubmit, register, handleSubmit, errors, apiError }) {
  return (
    <section className="auth-panel">
      <p className="eyebrow">Auriga Tiffin</p><h1>{title}</h1>
      {apiError && <p className="error">{apiError}</p>}
      <form className="form" onSubmit={handleSubmit(onSubmit)}>
        <label>Email or phone<input {...register('identifier', { required: 'Enter your email or phone.' })} autoComplete="username" /></label>
        {errors.identifier && <p className="error">{errors.identifier.message}</p>}
        <label>Password<input type="password" {...register('password', { required: 'Enter your password.' })} autoComplete="current-password" /></label>
        {errors.password && <p className="error">{errors.password.message}</p>}
        <button className="button" type="submit" disabled={loading}>{loading ? 'Logging in...' : submit}</button>
      </form>
      <p className="muted">New to Auriga? <Link to="/register">Create an account</Link></p>
    </section>
  )
}