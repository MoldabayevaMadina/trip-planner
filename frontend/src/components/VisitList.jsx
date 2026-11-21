import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { CATEGORIES, CATEGORY_ICONS } from '../utils/places'
import { formatDay } from '../utils/dates'

/** The plan of a day. ✎ turns a row into a small edit form. The numbers match the pins on the map. */
export default function VisitList({ visits, days, onToggle, onDelete, onSave }) {
  const [editingId, setEditingId] = useState(null)

  if (visits.length === 0) {
    return <div className="empty">No places for this day yet. Add the first one above.</div>
  }

  return (
    <ol className="visit-list">
      {visits.map((visit, index) =>
        editingId === visit.id ? (
          <VisitEditor
            key={visit.id}
            visit={visit}
            number={index + 1}
            days={days}
            onCancel={() => setEditingId(null)}
            onSave={async (changes) => {
              await onSave(visit, changes)      // if it throws, the editor stays open and shows the error
              setEditingId(null)
            }}
          />
        ) : (
          <li key={visit.id} className={`card visit ${visit.visited ? 'done' : ''}`}>
            <span className="visit-num">{index + 1}</span>
            <input type="checkbox" checked={visit.visited} onChange={() => onToggle(visit)} title="Visited" />
            <div className="trip-card-body">
              <div className="visit-name">{CATEGORY_ICONS[visit.category]} {visit.name}</div>
              {visit.address && <div className="small">{visit.address}</div>}
            </div>
            {visit.time && <span className="pill past">{visit.time.slice(0, 5)}</span>}
            <button type="button" className="icon-btn edit" title="Edit" onClick={() => setEditingId(visit.id)}>
              ✎
            </button>
            <button type="button" className="icon-btn" title="Remove from this day" onClick={() => onDelete(visit)}>
              ✕
            </button>
          </li>
        ),
      )}
    </ol>
  )
}

function VisitEditor({ visit, number, days, onSave, onCancel }) {
  const [values, setValues] = useState({
    name: visit.name,
    category: visit.category,
    time: visit.time ? visit.time.slice(0, 5) : '',   // "16:00:00" → "16:00" for <input type="time">
    day: visit.day,
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  // In how many days (of any trip) this place is planned. More than 1 → the place is shared.
  const usage = useApi(`/places/${visit.place}/days/`)
  const otherDays = usage.data ? usage.data.length - 1 : 0

  function change(field) {
    return (event) => {
      const value = field === 'day' ? Number(event.target.value) : event.target.value
      setValues((old) => ({ ...old, [field]: value }))
    }
  }

  async function submit(event) {
    event.preventDefault()
    if (!values.name.trim()) {
      setError('Enter a name.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave({ ...values, name: values.name.trim() })
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <li className="card visit-edit">
      <form className="visit-edit-form" onSubmit={submit}>
        <span className="visit-num">{number}</span>
        <input value={values.name} onChange={change('name')} placeholder="Name" autoFocus />
        <select value={values.category} onChange={change('category')}>
          {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <input type="time" value={values.time} onChange={change('time')} />
        <select value={values.day} onChange={change('day')} title="Move to another day">
          {days.map((day, index) => (
            <option key={day.id} value={day.id}>Day {index + 1} · {formatDay(day.date)}</option>
          ))}
        </select>

        {otherDays > 0 && (
          <p className="hint full-row">
            This place is also planned in {otherDays} other day{otherDays === 1 ? '' : 's'}.
            A new name or category will be shown there too.
          </p>
        )}
        {error && <p className="error full-row">{error}</p>}

        <div className="form-actions full-row">
          <button type="button" className="btn secondary" onClick={onCancel}>Cancel</button>
          <button className="btn" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </li>
  )
}