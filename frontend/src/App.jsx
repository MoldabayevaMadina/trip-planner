import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { useAuth } from './auth/useAuth'
import ProtectedRoute from './auth/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import TripsPage from './pages/TripsPage'
import TripFormPage from './pages/TripFormPage'
import TripPage from './pages/TripPage'
import ProfilePage from './pages/ProfilePage'
import HomePage from './pages/HomePage'


export default function App() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <>
      <header className="topbar">
        {/* <Link to={user ? '/trips' : '/'} className="brand">🧭 <span>Trip Planner</span></Link> */}
        <Link to="/" className="brand">🧭 <span>Trip Planner</span></Link>
        <nav>
          {user && <NavLink to="/trips">My trips</NavLink>}
          {user && <NavLink to="/profile">Profile</NavLink>}
        </nav>

        <div className="topbar-user">
          {user ? (
            <>
              <Link to="/profile" className="user-chip">👤 {user.username}</Link>
              <button type="button" className="btn secondary small-btn" onClick={handleLogout}>Log out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn secondary small-btn">Log in</Link>
              <Link to="/login?mode=signup" className="btn small-btn">Sign up</Link>
            </>
          )}
        </div>
      </header>

      <main className="container">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* only for logged-in users */}
          <Route element={<ProtectedRoute />}>
            <Route path="/trips" element={<TripsPage />} />
            <Route path="/trips/new" element={<TripFormPage />} />
            <Route path="/trips/:id" element={<TripPage />} />
            <Route path="/trips/:id/edit" element={<TripFormPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>

          <Route path="*" element={<p className="empty">Page not found.</p>} />
        </Routes>
      </main>
    </>
  )
}