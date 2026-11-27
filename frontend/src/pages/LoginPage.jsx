import { useState } from 'react'
import { Navigate, useLocation, useSearchParams } from 'react-router-dom'
import Field from '../components/Field'
import { useAuth } from '../auth/useAuth'

const EMPTY = { username: '', email: '', password: '', password2: '' }
const SERVER_FIELDS = ['username', 'email', 'password']

/** /login — log in; /login?mode=signup — create an account. */
export default function LoginPage() {
  const { user, login, register } = useAuth()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const mode = params.get('mode') === 'signup' ? 'signup' : 'login'

  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  // where to go after login: the protected page the user wanted, or "My trips"
  const from = location.state?.from
  const nextPage = from ? from.pathname + (from.search ?? '') : '/trips'

  // logged in (now or earlier) → leave this page
  if (user) return <Navigate to={nextPage} replace />

  
  function switchMode(next) {
    setParams(next === 'signup' ? { mode: 'signup' } : {}, { replace: true, state: location.state })
    setValues(EMPTY)         
    setErrors({})
    setShowPassword(false)
  }

  function change(event) {
    const { name, value } = event.target
    setValues((old) => ({ ...old, [name]: value }))
    setErrors((old) => ({ ...old, [name]: undefined, form: undefined }))
  }

  function validate() {
    const found = {}
    if (!values.username.trim()) found.username = 'Enter a username.'
    if (!values.password) found.password = 'Enter a password.'
    if (mode === 'signup') {
      if (values.email && !/^\S+@\S+\.\S+$/.test(values.email)) found.email = 'Enter a valid email.'
      if (values.password && values.password.length < 8) found.password = 'At least 8 characters.'
      if (values.password2 !== values.password) found.password2 = "The passwords don't match."
    }
    return found
  }

  async function submit(event) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSaving(true)
    try {
      if (mode === 'login') {
        await login(values.username.trim(), values.password)
      } else {
        await register({ username: values.username.trim(), email: values.email.trim(), password: values.password })
      }
      // success: `user` is set → this page re-renders and <Navigate> above takes us further
    } catch (error) {
      if (mode === 'login' && error.status === 401) {
        setErrors({ form: 'Wrong username or password.' })
      } else if (error.status === 400 && error.data) {
        setErrors(toFieldErrors(error.data))     // e.g. "A user with that username already exists."
      } else {
        setErrors({ form: error.message })        // server or network problem
      }
      setSaving(false)
    }
  }

  const isLogin = mode === 'login'

  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="auth-brand">🧭 <span>Trip Planner</span></div>
        <p className="muted auth-tagline">Plan trips day by day: places on a map and the weather for every day.</p>

        <div className="chips auth-tabs">
          <button type="button" className={`chip ${isLogin ? 'active' : ''}`} onClick={() => switchMode('login')}>
            Log in
          </button>
          <button type="button" className={`chip ${!isLogin ? 'active' : ''}`} onClick={() => switchMode('signup')}>
            Sign up
          </button>
        </div>

        <form key={mode} className="auth-form" onSubmit={submit} noValidate>
          <Field label="Username" error={errors.username}>
            <input name="username" value={values.username} onChange={change} autoComplete="username" autoFocus />
          </Field>

          {!isLogin && (
            <Field label="Email" hint="Optional" error={errors.email}>
              <input type="email" name="email" value={values.email} onChange={change} autoComplete="email" />
            </Field>
          )}

          <Field
            label="Password"
            hint={!isLogin ? 'At least 8 characters, not only digits, not too common' : undefined}
            error={errors.password}
          >
            <div className="password-field">
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={values.password}
                onChange={change}
                autoComplete={isLogin ? 'current-password' : 'new-password'}
              />
              <button
                type="button"
                className="icon-btn"
                onClick={() => setShowPassword((shown) => !shown)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? '🙈' : '👁'}
              </button>
            </div>
          </Field>

          {!isLogin && (
            <Field label="Repeat password" error={errors.password2}>
              <input
                type={showPassword ? 'text' : 'password'}
                name="password2"
                value={values.password2}
                onChange={change}
                autoComplete="new-password"
              />
            </Field>
          )}

          {errors.form && <p className="error">{errors.form}</p>}

          <button className="btn auth-submit" disabled={saving}>
            {saving
              ? (isLogin ? 'Logging in…' : 'Creating your account…')
              : (isLogin ? 'Log in' : 'Create account')}
          </button>
        </form>

        <p className="muted auth-switch">
          {isLogin ? 'No account yet?' : 'Already have an account?'}
          <button type="button" className="link-btn" onClick={() => switchMode(isLogin ? 'signup' : 'login')}>
            {isLogin ? 'Sign up' : 'Log in'}
          </button>
        </p>
      </div>
    </div>
  )
}

/** {"username": ["msg"], "non_field_errors": ["msg"]} → {username: "msg", form: "msg"} */
function toFieldErrors(data) {
  const result = {}
  for (const [field, messages] of Object.entries(data)) {
    const text = [].concat(messages).join(' ')
    if (SERVER_FIELDS.includes(field)) result[field] = text
    else result.form = text
  }
  return result
}