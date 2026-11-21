import { Link, NavLink, Route, Routes } from 'react-router-dom'
import TripsPage from './pages/TripsPage'
import TripFormPage from './pages/TripFormPage'
import TripPage from './pages/TripPage'

export default function App() {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">🧭 <span>Trip Planner</span></Link>
        <nav>
          <NavLink to="/" end>Trips</NavLink>
        </nav>
      </header>

      <main className="container">
        <Routes>
          <Route path="/" element={<TripsPage />} />
          <Route path="/trips/new" element={<TripFormPage />} />
          <Route path="/trips/:id" element={<TripPage />} />
          <Route path="/trips/:id/edit" element={<TripFormPage />} />
          <Route path="*" element={<p className="empty">Page not found.</p>} />
        </Routes>
      </main>
    </>
  )
}