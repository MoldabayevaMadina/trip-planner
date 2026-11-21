import { Link } from 'react-router-dom'
import { countdown, formatRange, tripDays } from '../utils/dates'

export default function TripCard({ trip }) {
  const when = countdown(trip.start_date, trip.end_date)
  const phase = when === 'Finished' ? 'past' : when === 'Now' ? 'now' : 'soon'

  return (
    <Link to={`/trips/${trip.id}`} className="card trip-card">
      <div className="city-badge">{trip.city.charAt(0).toUpperCase()}</div>

      <div className="trip-card-body">
        <div className="row">
          <h3>{trip.title}</h3>
          {trip.country?.visa_free && <span className="badge">🛂 visa-free</span>}
        </div>
        <p className="muted">
          {trip.city}{trip.country ? `, ${trip.country.name}` : ''}
        </p>
        <p className="small">
          {formatRange(trip.start_date, trip.end_date)} · {tripDays(trip.start_date, trip.end_date)} days
          · {trip.places_count} places
        </p>
      </div>

      <span className={`pill ${phase}`}>{when}</span>
    </Link>
  )
}