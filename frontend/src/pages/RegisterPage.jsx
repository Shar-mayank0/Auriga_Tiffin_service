import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function RegisterPage() {
  const { register, handleSubmit, watch, formState: { errors } } = useForm()
  const { register: createAccount, loading, isAuthenticated } = useAuth()
  const [error, setError] = useState('')
  const navigate = useNavigate()
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  const onSubmit = async ({ name, phone, password, password2 }) => {
    setError('')
    try {
      await createAccount({ username: phone, first_name: name, phone, password, password2 })
      navigate('/subscribe')
    } catch (requestError) {
      setError(Object.values(requestError.response?.data || {}).flat().join(' ') || 'Registration failed.')
    }
  }
  return (
    <section className="auth-panel">
      <p className="eyebrow">Start your service</p><h1>Create your account</h1>
      {error && <p className="error">{error}</p>}
      <form className="form" onSubmit={handleSubmit(onSubmit)}>
        <label>Name<input {...register('name', { required: 'Enter your name.' })} /></label>
        {errors.name && <p className="error">{errors.name.message}</p>}
        <label>Phone<input type="tel" {...register('phone', { required: 'Enter your phone.' })} /></label>
        {errors.phone && <p className="error">{errors.phone.message}</p>}
        <label>Password<input type="password" {...register('password', { required: 'Choose a password.', minLength: { value: 6, message: 'Use at least 6 characters.' } })} /></label>
        {errors.password && <p className="error">{errors.password.message}</p>}
        <label>Confirm password<input type="password" {...register('password2', { validate: (value) => value === watch('password') || 'Passwords do not match.' })} /></label>
        {errors.password2 && <p className="error">{errors.password2.message}</p>}
        <button className="button" type="submit" disabled={loading}>{loading ? 'Creating account...' : 'Create account'}</button>
      </form>
      <p className="muted">Already registered? <Link to="/login">Log in</Link></p>
    </section>
  )
}