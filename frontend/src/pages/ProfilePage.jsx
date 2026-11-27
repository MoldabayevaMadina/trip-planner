import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth/useAuth'
import { formatDate } from '../utils/dates'
import Field from '../components/Field'
import Modal from '../components/Modal'

/** /profile — who I am. Editing and the password change open in a dialog. Only for logged-in users. */
export default function ProfilePage() {
  const { user, setUser } = useAuth()
  const [dialog, setDialog] = useState(null)      // null | 'edit' | 'password'
  const [notice, setNotice] = useState(null)      // "✓ Profile updated" after a dialog is saved

  // fresh data when the page opens (e.g. the number of trips could have changed)
  useEffect(() => {
    api('/auth/me/').then(setUser).catch(() => {})
  }, [setUser])

  // the notice disappears after 4 seconds
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 4000)
    return () => clearTimeout(timer)
  }, [notice])

  const closeDialog = useCallback(() => setDialog(null), [])

  const profile = user.profile ?? {}

  return (
    <div className="profile-page">
      <div className="page-head">
        <h1>Profile</h1>
      </div>

      {notice && <p className="notice">{notice}</p>}

      <div className="card profile-card">
        <div className="avatar">{user.username.charAt(0).toUpperCase()}</div>
        <div className="trip-card-body">
          <h2>{user.username}</h2>
          <p className="muted">{user.email || 'No email'}</p>
          <p className="small">Member since {formatDate(user.date_joined.slice(0, 10))}</p>
        </div>
        <div className="profile-actions">
          <button type="button" className="btn" onClick={() => setDialog('edit')}>✎ Edit profile</button>
          <button type="button" className="btn secondary" onClick={() => setDialog('password')}>
            🔒 Change password
          </button>
        </div>
      </div>

      <div className="profile-grid">
        <div className="card">
          <h3>About</h3>
          <dl className="info-list">
            <dt>🏠 Home city</dt>
            <dd>{profile.home_city || <span className="muted">Not set</span>}</dd>
            <dt>💬 About me</dt>
            <dd>{profile.bio || <span className="muted">Tell other travellers about yourself</span>}</dd>
          </dl>
        </div>

        <div className="card stat-card">
          <h3>Trips</h3>
          <div className="stat-number">{user.trips_count}</div>
          <p className="muted">trip{user.trips_count === 1 ? '' : 's'} planned</p>
          <Link to="/trips" className="btn secondary">Open my trips →</Link>
        </div>
      </div>

      {dialog === 'edit' && (
        <Modal title="Edit profile" onClose={closeDialog}>
          <ProfileForm
            user={user}
            onCancel={closeDialog}
            onSaved={(updated) => {
              setUser(updated)              // the whole app sees the new data at once (e.g. the top bar)
              setDialog(null)
              setNotice('✓ Profile updated')
            }}
          />
        </Modal>
      )}

      {dialog === 'password' && (
        <Modal title="Change password" onClose={closeDialog}>
          <PasswordForm
            onCancel={closeDialog}
            onDone={() => {
              setDialog(null)
              setNotice('✓ Password changed')
            }}
          />
        </Modal>
      )}
    </div>
  )
}

/** {"field": ["msg"]} or {"profile": {"bio": ["msg"]}} → {field: "msg", bio: "msg"} */
function flatErrors(data) {
  const { profile, ...rest } = data
  const all = { ...rest, ...(profile ?? {}) }
  return Object.fromEntries(Object.entries(all).map(([key, value]) => [key, [].concat(value).join(' ')]))
}

function ProfileForm({ user, onSaved, onCancel }) {
  const [values, setValues] = useState({
    username: user.username,
    email: user.email ?? '',
    home_city: user.profile?.home_city ?? '',
    bio: user.profile?.bio ?? '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  function change(event) {
    const { name, value } = event.target
    setValues((old) => ({ ...old, [name]: value }))
    setErrors((old) => ({ ...old, [name]: undefined, form: undefined }))
  }

  async function submit(event) {
    event.preventDefault()
    if (!values.username.trim()) {
      setErrors({ username: 'Enter a username.' })
      return
    }
    setSaving(true)
    try {
      const updated = await api('/auth/me/', {
        method: 'PATCH',
        body: {
          username: values.username.trim(),
          email: values.email.trim(),
          profile: { home_city: values.home_city.trim(), bio: values.bio.trim() },
        },
      })
      onSaved(updated)
    } catch (error) {
      setErrors(error.status === 400 && error.data ? flatErrors(error.data) : { form: error.message })
      setSaving(false)
    }
  }

  return (
    <form className="form modal-form" onSubmit={submit} noValidate>
      <Field label="Username" error={errors.username}>
        <input name="username" value={values.username} onChange={change} autoComplete="username" autoFocus />
      </Field>
      <Field label="Email" error={errors.email}>
        <input type="email" name="email" value={values.email} onChange={change} autoComplete="email" />
      </Field>
      <Field label="Home city" error={errors.home_city}>
        <input name="home_city" value={values.home_city} onChange={change} placeholder="Almaty" />
      </Field>
      <Field label="About me" hint="Up to 500 characters" error={errors.bio}>
        <textarea name="bio" rows={3} maxLength={500} value={values.bio} onChange={change} />
      </Field>

      {errors.form && <p className="error">{errors.form}</p>}
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
      </div>
    </form>
  )
}

const EMPTY_PASSWORDS = { old_password: '', new_password: '', new_password2: '' }

function PasswordForm({ onDone, onCancel }) {
  const [values, setValues] = useState(EMPTY_PASSWORDS)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  function change(event) {
    const { name, value } = event.target
    setValues((old) => ({ ...old, [name]: value }))
    setErrors((old) => ({ ...old, [name]: undefined, form: undefined }))
  }

  async function submit(event) {
    event.preventDefault()
    const found = {}
    if (!values.old_password) found.old_password = 'Enter your current password.'
    if (values.new_password.length < 8) found.new_password = 'At least 8 characters.'
    if (values.new_password2 !== values.new_password) found.new_password2 = "The passwords don't match."
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSaving(true)
    try {
      await api('/auth/change-password/', {
        method: 'POST',
        body: { old_password: values.old_password, new_password: values.new_password },
      })
      onDone()
    } catch (error) {
      setErrors(error.status === 400 && error.data ? flatErrors(error.data) : { form: error.message })
      setSaving(false)
    }
  }

  return (
    <form className="form modal-form" onSubmit={submit} noValidate>
      <Field label="Current password" error={errors.old_password}>
        <input type="password" name="old_password" value={values.old_password} onChange={change}
               autoComplete="current-password" autoFocus />
      </Field>
      <Field label="New password" hint="At least 8 characters, not only digits, not too common" error={errors.new_password}>
        <input type="password" name="new_password" value={values.new_password} onChange={change}
               autoComplete="new-password" />
      </Field>
      <Field label="Repeat new password" error={errors.new_password2}>
        <input type="password" name="new_password2" value={values.new_password2} onChange={change}
               autoComplete="new-password" />
      </Field>

      {errors.form && <p className="error">{errors.form}</p>}
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={saving}>{saving ? 'Saving…' : 'Change password'}</button>
      </div>
    </form>
  )
}