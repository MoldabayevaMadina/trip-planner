import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../auth/useAuth'
import { CATEGORY_ICONS } from '../utils/places'

const FEATURES = [
  ['🗺', 'Day-by-day map', 'Every day of a trip has its own plan, pins and route on the map.'],
  ['☀️', 'Weather for every day', 'A forecast for the next two weeks, the same dates last year for later trips.'],
  ['🛂', 'Visa-free countries', 'See at a glance which trips need no visa.'],
  ['📊', 'Progress', 'Tick off places you visited and see how much of the plan is done.'],
]

/** "TR" → 🇹🇷 (a flag is two "regional indicator" letters) */
function flag(code) {
  return code.toUpperCase().replace(/./g, (letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)))
}

/** / — public: what the app does + data from the public API (popular places, visa-free countries). */
export default function HomePage() {
  const { user } = useAuth()
  const popular = useApi('/places/popular/?limit=6')
  const visaFree = useApi('/countries/?visa_free=true')

  return (
    <div className="home">
      <section className="hero">
        <h1>Plan your trips <span>day by day</span></h1>
        <p className="hero-text">
          Places on a map, the weather for every day and visa-free countries - all in one planner.
        </p>
        <div className="hero-actions">
          {user ? (
            <Link to="/trips" className="btn big-btn">Open my trips →</Link>
          ) : (
            <>
              <Link to="/login?mode=signup" className="btn big-btn">Get started - it's free</Link>
              <Link to="/login" className="btn secondary big-btn">Log in</Link>
            </>
          )}
        </div>
      </section>

      <section className="features">
        {FEATURES.map(([icon, title, text]) => (
          <div key={title} className="card feature">
            <div className="feature-icon">{icon}</div>
            <h3>{title}</h3>
            <p className="muted">{text}</p>
          </div>
        ))}
      </section>

      <section>
        <h2 className="section-title">Popular places among travellers</h2>
        {popular.loading && <p className="muted">Loading…</p>}
        {popular.error && <p className="error">{popular.error.message}</p>}
        {popular.data?.length === 0 && <p className="muted">No popular places yet.</p>}
        <div className="popular-grid">
          {popular.data?.map((place, index) => (
            <div key={place.id} className="card popular-place">
              <span className="visit-num">{index + 1}</span>
              <div className="trip-card-body">
                <div className="visit-name">{CATEGORY_ICONS[place.category]} {place.name}</div>
                <div className="small">{place.address}</div>
              </div>
              <span className="pill soon">{place.trips_count} trip{place.trips_count === 1 ? '' : 's'}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="section-title">Visa-free countries</h2>
        {visaFree.error && <p className="error">{visaFree.error.message}</p>}
        <div className="country-chips">
          {visaFree.data?.map((country) => (
            <span key={country.id} className="country-chip">
              {flag(country.code)} {country.name}
              {country.visa_free_days && <b> · {country.visa_free_days} days</b>}
            </span>
          ))}
        </div>
        <p className="warning-text">⚠ Visa rules change: always check the official rules before a trip.</p>
      </section>
    </div>
  )
}