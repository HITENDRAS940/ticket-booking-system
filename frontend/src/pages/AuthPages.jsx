import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

function AuthForm({ mode }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'customer' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event) => {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      if (mode === 'login') await login({ email: form.email, password: form.password })
      else await register(form)
      navigate(location.state?.from?.pathname || '/')
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return <div className="mx-auto max-w-md">
    <h1 className="page-title mb-6">{mode === 'login' ? 'Log in' : 'Create account'}</h1>
    <form onSubmit={submit} className="panel space-y-4">
      {error && <p className="error">{error}</p>}
      {mode === 'register' && <><div><label>Name</label><input required minLength="2" value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} /></div>
        <div><label>Account type</label><select value={form.role} onChange={(e) => setForm({...form, role: e.target.value})}><option value="customer">Customer</option><option value="organiser">Organiser</option></select></div></>}
      <div><label>Email</label><input required type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} /></div>
      <div><label>Password</label><input required type="password" minLength={mode === 'register' ? 8 : undefined} value={form.password} onChange={(e) => setForm({...form, password: e.target.value})} /></div>
      <button disabled={busy} className="btn w-full">{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Register'}</button>
      <p className="text-center text-sm text-gray-600">{mode === 'login' ? <>No account? <Link className="text-amber-600 underline" to="/register">Register</Link></> : <>Have an account? <Link className="text-amber-600 underline" to="/login">Log in</Link></>}</p>
    </form>
  </div>
}

export const LoginPage = () => <AuthForm mode="login" />
export const RegisterPage = () => <AuthForm mode="register" />

