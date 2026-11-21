import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useApi } from '../hooks/useApi'
import { countdown, formatDayLong, formatRange, tripDays } from '../utils/dates'
import DayStrip from '../components/DayStrip'
import AddPlaceForm from '../components/AddPlaceForm'
import VisitList from '../components/VisitList'
import TripMap from '../components/TripMap'
import ConfirmDialog from '../components/ConfirmDialog'

export default function TripPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [picked, setPicked] = useState(null)          // [lat, lng] of a click on the map

  // GET /api/trips/{id}/days/ → { trip, days: [{ id, date, weather, visits: [...] }], weather_available }
  const plan = useApi(`/trips/${id}/days/`)

  if (plan.error) {
    return (
      <div className="empty">
        <p>{plan.error.status === 404 ? 'This trip no longer exists.' : plan.error.message}</p>
        <Link to="/" className="btn secondary">Back to trips</Link>
      </div>
    )
  }
  if (!plan.data) return <p className="muted">Loading the plan and the weather…</p>

  const { trip, days, weather_available } = plan.data
  const selectedId = Number(params.get('day')) || days[0]?.id
  const day = days.find((d) => d.id === selectedId) ?? days[0]

  /** Runs a change on the server, then loads the plan again so every part of the page is up to date. */
  async function run(change) {
    setActionError(null)
    try {
      await change()
      plan.reload()
    } catch (error) {
      setActionError(error.message)
    }
  }

  async function deleteTrip() {
    try {
      await api(`/trips/${trip.id}/`, { method: 'DELETE' })
      navigate('/')
    } catch (error) {
      setConfirmDelete(false)
      setActionError(error.message)
    }
  }

  async function addPlace(body) {
    await api(`/days/${day.id}/visits/`, { method: 'POST', body })   // errors are shown by the form
    setPicked(null)
    plan.reload()
  }

    /**
   * Saves the edit form of a visit with up to two requests:
   * the place itself (name, category) and the visit (time, day).
   * Errors are thrown, so the edit form shows them.
   */
  async function saveVisit(visit, { name, category, time, day: dayId }) {
    if (name !== visit.name || category !== visit.category) {
      await api(`/places/${visit.place}/`, { method: 'PATCH', body: { name, category } })
    }

    const changes = {}
    const oldTime = visit.time ? visit.time.slice(0, 5) : ''
    if (time !== oldTime) changes.time = time || null      // empty field → no time
    if (dayId !== visit.day) changes.day = dayId           // move to another day of this trip
    if (Object.keys(changes).length > 0) {
      await api(`/visits/${visit.id}/`, { method: 'PATCH', body: changes })
    }

    plan.reload()
  }

  function selectDay(dayId) {
    setPicked(null)
    setParams({ day: dayId })
  }

  return (
    <>
      <Link to="/" className="back">← All trips</Link>

      <div className="card trip-head">
        <div className="city-badge">{trip.city.charAt(0).toUpperCase()}</div>
        <div className="trip-card-body">
          <div className="row">
            <h1>{trip.title}</h1>
            {trip.country?.visa_free && <span className="badge">🛂 visa-free</span>}
          </div>
          <p className="muted">{trip.city}{trip.country ? `, ${trip.country.name}` : ''}</p>
          <p className="small">
            {formatRange(trip.start_date, trip.end_date)} · {tripDays(trip.start_date, trip.end_date)} days
            · {countdown(trip.start_date, trip.end_date)}
          </p>
        </div>
        <div className="row">
          <Link to={`/trips/${trip.id}/edit`} className="btn secondary">Edit</Link>
          <button type="button" className="btn danger" onClick={() => setConfirmDelete(true)}>Delete</button>
        </div>
      </div>

      {!weather_available && (
        <p className="hint">Weather service is unavailable right now. The plan works, the weather will appear later.</p>
      )}
      {actionError && <p className="error">{actionError}</p>}

      <DayStrip days={days} selectedId={day?.id} onSelect={selectDay} />

            {day && (
        <section className="day-section">
          <div className="day-head">
            <h2>{formatDayLong(day.date)}</h2>
            {day.weather && (
              <span className="muted">
                {day.weather.icon} {day.weather.text}
                {day.weather.temp_max != null &&
                  ` · ${Math.round(day.weather.temp_max)}° / ${Math.round(day.weather.temp_min)}°`}
              </span>
            )}
          </div>

          {day.weather?.rainy && (
            <p className="hint">🌧 Rain is expected. Maybe plan museums and indoor places for this day.</p>
          )}
          {day.weather?.source === 'last_year' && (
            <p className="hint">Too far for a forecast: this is the weather on the same dates last year.</p>
          )}

          <TripMap
            center={[trip.latitude, trip.longitude]}
            visits={day.visits}
            picked={picked}
            onPick={setPicked}
          />

          <AddPlaceForm
            key={picked ? 'point' : 'name'}          // a fresh form when switching between the two modes
            city={trip.city}
            point={picked}
            onAdd={addPlace}
            onCancelPoint={() => setPicked(null)}
          />

          
          <VisitList
            visits={day.visits}
            days={days}
            onToggle={(visit) =>
              run(() => api(`/visits/${visit.id}/`, { method: 'PATCH', body: { visited: !visit.visited } }))}
            onDelete={(visit) =>
              run(() => api(`/visits/${visit.id}/`, { method: 'DELETE' }))}
            onSave={saveVisit}
          />
        </section>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Delete trip?"
          text={`"${trip.title}" with all its days and plans will be deleted. Places stay in the catalog.`}
          onConfirm={deleteTrip}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </>
  )
}