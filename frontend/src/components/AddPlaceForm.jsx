import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { useDebounced } from '../hooks/useDebounced'
import { CATEGORIES } from '../utils/places'

/**
 * Adds a place to the day.
 * - typing a name shows suggestions near the trip's city; a picked one is added with its exact
 *   coordinates, address and osm_id;
 * - Add without picking: the server searches by name (the first result);
 * - with `point` (a click on the map): by coordinates, no search.
 */
export default function AddPlaceForm({ tripId, city, point, onAdd, onCancelPoint }) {
  const [name, setName] = useState('')
  const [category, setCategory] = useState(point ? 'other' : 'sight')
  const [time, setTime] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const [chosen, setChosen] = useState(null)   // the picked suggestion
  const [open, setOpen] = useState(false)      // is the dropdown open
  const [active, setActive] = useState(-1)     // highlighted row for the keyboard

  // search only in "by name" mode, after 3 letters, 300 ms after the last key press
  const query = useDebounced(name.trim(), 300)
  const searchPath = !point && !chosen && query.length >= 3
    ? `/places/suggest/?q=${encodeURIComponent(query)}&trip=${tripId}`
    : null
  const suggestions = useApi(searchPath)
  const items = suggestions.data ?? []
  const showList = open && searchPath !== null

  function typeName(event) {
    setName(event.target.value)
    setChosen(null)          // the text changed → the picked place no longer matches
    setOpen(true)
    setActive(-1)
  }

  function choose(item) {
    setChosen(item)
    setName(item.name)
    setOpen(false)
  }

  function onKeyDown(event) {
    if (!showList || items.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => Math.min(i + 1, items.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()   // pick the row instead of submitting the form
      choose(items[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  async function submit(event) {
    event.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError(null)

    const body = { name: name.trim(), category, ...(time ? { time } : {}) }
    if (point) {
      body.latitude = Number(point[0].toFixed(6))
      body.longitude = Number(point[1].toFixed(6))
    } else if (chosen) {
      body.latitude = chosen.latitude
      body.longitude = chosen.longitude
      body.address = chosen.address
      if (chosen.osm_id) body.osm_id = chosen.osm_id
    }

    try {
      await onAdd(body)
      setName('')
      setTime('')
      setChosen(null)
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

      <div className="combo">
        <input
          placeholder={point ? 'Name this point, e.g. "Our hotel"' : `Find a place in ${city}: a museum, a café, a park…`}
          value={name}
          onChange={typeName}
          onKeyDown={onKeyDown}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          autoFocus={Boolean(point)}
          role="combobox"
          aria-expanded={showList}
          aria-autocomplete="list"
        />

        {showList && (
          <ul className="suggestions" role="listbox">
            {suggestions.loading && <li className="suggestion muted">Searching…</li>}
            {suggestions.error && <li className="suggestion muted">Search is unavailable right now.</li>}
            {suggestions.data && items.length === 0 && (
              <li className="suggestion muted">Nothing found nearby. Press Add to search by name, or click on the map.</li>
            )}
            {items.map((item, index) => (
              <li
                key={`${item.osm_id}-${index}`}
                role="option"
                aria-selected={index === active}
                className={`suggestion ${index === active ? 'active' : ''}`}
                onMouseEnter={() => setActive(index)}
                // mousedown, not click: it fires before the input loses focus and closes the list
                onMouseDown={(e) => {
                  e.preventDefault()
                  choose(item)
                }}
              >
                <span className="suggestion-name">{item.name}</span>
                {item.address && <span className="small">{item.address}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {chosen && (
        <p className="full-row small chosen">
          ✓ {chosen.address || 'Picked from the list'}
          <button type="button" className="link-btn" onClick={() => setChosen(null)}>change</button>
        </p>
      )}

      <select value={category} onChange={(e) => setCategory(e.target.value)}>
        {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
      <button className="btn" disabled={saving || !name.trim()}>
        {saving ? 'Adding…' : 'Add'}
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