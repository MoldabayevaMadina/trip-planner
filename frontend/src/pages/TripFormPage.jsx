import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useApi } from '../hooks/useApi'
import { tripDays } from '../utils/dates'
import Field from '../components/Field'

const MAX_DAYS = 30
const FIELDS = ['city', 'title', 'start_date', 'end_date']

/** /trips/new → empty form; /trips/:id/edit → load the trip first, then show the form. */
export default function TripFormPage() {
  const { id } = useParams()
  return id ? <EditTrip id={id} /> : <TripForm />
}

function EditTrip({ id }) {
  const trip = useApi(`/trips/${id}/`)
  if (trip.error) return <p className="error">{trip.error.message}</p>
  if (!trip.data) return <p className="muted">Loading…</p>
  return <TripForm trip={trip.data} />
}

function TripForm({ trip }) {
  const navigate = useNavigate()
  const isEdit = Boolean(trip)
  const backTo = isEdit ? `/trips/${trip.id}` : '/'

  const [values, setValues] = useState({
    city: trip?.city ?? '',
    title: trip?.title ?? '',
    start_date: trip?.start_date ?? '',
    end_date: trip?.end_date ?? '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  function change(event) {
    const { name, value } = event.target
    setValues((old) => ({ ...old, [name]: value }))
    setErrors((old) => ({ ...old, [name]: undefined, form: undefined }))   // hide the error while typing
  }

  /** The same rules as the serializer, so most mistakes are shown without a request. */
  function validate() {
    const found = {}
    if (!values.city.trim()) found.city = 'Enter a city.'
    if (!values.start_date) found.start_date = 'Pick a start date.'
    if (!values.end_date) found.end_date = 'Pick an end date.'
    if (values.start_date && values.end_date) {
      if (values.end_date < values.start_date) {
        found.end_date = "End date can't be before start date."
      } else if (tripDays(values.start_date, values.end_date) > MAX_DAYS) {
        found.end_date = `A trip can be at most ${MAX_DAYS} days long.`
      }
    }
    return found
  }

  async function submit(event) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSaving(true)
    const body = {
      city: values.city.trim(),
      title: values.title.trim() || values.city.trim(),
      start_date: values.start_date,
      end_date: values.end_date,
    }
    try {
      const saved = isEdit
        ? await api(`/trips/${trip.id}/`, { method: 'PATCH', body })
        : await api('/trips/', { method: 'POST', body })
      navigate(`/trips/${saved.id}`)
    } catch (error) {
      // 400 → {"city": ["Couldn't find ..."]} under the field; 503 and others → above the buttons
      setErrors(error.status === 400 && error.data ? toFieldErrors(error.data) : { form: error.message })
      setSaving(false)
    }
  }

  const days = values.start_date && values.end_date && values.end_date >= values.start_date
    ? tripDays(values.start_date, values.end_date)
    : null

  return (
    <div className="form-page">
      <Link to={backTo} className="back">← Back</Link>
      <h1>{isEdit ? 'Edit trip' : 'New trip'}</h1>
      <p className="muted">
        We find the city on the map, link its country and create a day for every date.
      </p>

      <form className="card form" onSubmit={submit} noValidate>
        <Field label="City *" error={errors.city}>
          <input name="city" value={values.city} onChange={change} placeholder="Istanbul" autoFocus />
        </Field>

        <Field label="Title" hint="Optional — the city is used if empty" error={errors.title}>
          <input name="title" value={values.title} onChange={change} placeholder="Istanbul with friends" />
        </Field>

        <div className="form-row">
          <Field label="Start *" error={errors.start_date}>
            <input type="date" name="start_date" value={values.start_date} onChange={change} />
          </Field>
          <Field label="End *" error={errors.end_date}>
            <input type="date" name="end_date" value={values.end_date} min={values.start_date} onChange={change} />
          </Field>
        </div>

        {days && <p className="days-preview">🗓 {days} day{days === 1 ? '' : 's'}</p>}
        {errors.form && <p className="error">{errors.form}</p>}

        <div className="form-actions">
          <Link to={backTo} className="btn secondary">Cancel</Link>
          <button className="btn" disabled={saving}>
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Create trip'}
          </button>
        </div>
      </form>
    </div>
  )
}

/** {"end_date": ["msg"], "non_field_errors": ["msg"]} → {end_date: "msg", form: "msg"} */
function toFieldErrors(data) {
  const result = {}
  for (const [field, messages] of Object.entries(data)) {
    const text = [].concat(messages).join(' ')
    if (FIELDS.includes(field)) result[field] = text
    else result.form = text
  }
  return result
}