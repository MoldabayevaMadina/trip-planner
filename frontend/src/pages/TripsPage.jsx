import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import TripCard from '../components/TripCard'

const STATUSES = [
  ['', 'All'],
  ['upcoming', 'Upcoming'],
  ['current', 'Now'],
  ['past', 'Past'],
]

const ORDERINGS = [
  ['', 'Start date (soonest)'],
  ['-start_date', 'Start date (latest)'],
  ['title', 'Title A–Z'],
  ['-created_at', 'Recently added'],
]

export default function TripsPage() {
  // Filters live in the address bar: /?status=upcoming&country=TR
  // → the page can be reloaded or shared, and "Back" returns to the previous filters.
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('search') ?? '')

  const trips = useApi(`/trips/?${params}`)     // the same query string goes to Django
  const countries = useApi('/countries/')

  function setParam(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    setParams(next)
  }

  function submitSearch(event) {
    event.preventDefault()          // a form submit would reload the page otherwise
    setParam('search', search.trim())
  }

  function resetFilters() {
    setSearch('')
    setParams({})
  }

  const hasFilters = params.toString() !== ''

  return (
    <>
      <div className="page-head">
        <h1>My trips</h1>
        <Link to="/trips/new" className="btn">+ New trip</Link>
      </div>

      <div className="filters">
        <form onSubmit={submitSearch} className="row">
          <input
            type="search"
            placeholder="Search by title or city"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="btn secondary">Search</button>
        </form>

        <div className="chips">
          {STATUSES.map(([value, label]) => (
            <button
              key={label}
              type="button"
              className={`chip ${(params.get('status') ?? '') === value ? 'active' : ''}`}
              onClick={() => setParam('status', value)}
            >
              {label}
            </button>
          ))}
        </div>

        <select value={params.get('country') ?? ''} onChange={(e) => setParam('country', e.target.value)}>
          <option value="">All countries</option>
          {countries.data?.map((country) => (
            <option key={country.id} value={country.code}>{country.name}</option>
          ))}
        </select>

        <label className="row">
          <input
            type="checkbox"
            checked={params.get('visa_free') === 'true'}
            onChange={(e) => setParam('visa_free', e.target.checked ? 'true' : '')}
          />
          Visa-free only
        </label>

        <select value={params.get('ordering') ?? ''} onChange={(e) => setParam('ordering', e.target.value)}>
          {ORDERINGS.map(([value, label]) => (
            <option key={label} value={value}>{label}</option>
          ))}
        </select>

        {hasFilters && (
          <button type="button" className="btn secondary" onClick={resetFilters}>Reset</button>
        )}
      </div>

      {trips.error && <p className="error">{trips.error.message}</p>}
      {trips.loading && <p className="muted">Loading…</p>}
      {trips.data?.length === 0 && (
        <div className="empty">
          {hasFilters ? 'No trips match the filters.' : 'No trips yet. Plan your first one!'}
        </div>
      )}

      <div className="list">
        {trips.data?.map((trip) => <TripCard key={trip.id} trip={trip} />)}
      </div>
    </>
  )
}