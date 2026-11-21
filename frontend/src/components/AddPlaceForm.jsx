import { useState } from 'react'
import { CATEGORIES } from '../utils/places'

/**
 * Adds a place to the day.
 * - without `point`: by name, the server finds it on the map near the trip's city;
 * - with `point` (a click on the map): by coordinates, no search needed.
 */
export default function AddPlaceForm({ city, point, onAdd, onCancelPoint }) {
  const [name, setName] = useState('')
  const [category, setCategory] = useState(point ? 'other' : 'sight')
  const [time, setTime] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit(event) {
    event.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    const body = { name: name.trim(), category, ...(time ? { time } : {}) }
    if (point) {
      body.latitude = Number(point[0].toFixed(6))
      body.longitude = Number(point[1].toFixed(6))
    }
    try {
      await onAdd(body)
      setName('')
      setTime('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={`add-place ${point ? 'picked' : ''}`} onSubmit={submit}>
      {point && (
        <p className="full-row small">
          📍 Point on the map: {point[0].toFixed(5)}, {point[1].toFixed(5)}
        </p>
      )}
      <input
        placeholder={point ? 'Name this point, e.g. "Our hotel"' : `Add a place in ${city}: a museum, a café, a park…`}
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoFocus={Boolean(point)}
      />
      <select value={category} onChange={(e) => setCategory(e.target.value)}>
        {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
      <button className="btn" disabled={saving || !name.trim()}>
        {saving ? (point ? 'Adding…' : 'Finding…') : 'Add'}
      </button>
      {point && (
        <button type="button" className="btn secondary full-row" onClick={onCancelPoint}>
          Cancel the point — search by name instead
        </button>
      )}
      {error && <p className="error full-row">{error}</p>}
    </form>
  )
}