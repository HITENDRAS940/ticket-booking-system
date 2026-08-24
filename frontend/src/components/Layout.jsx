import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const navClass = ({ isActive }) => `text-sm ${isActive ? 'font-semibold text-black' : 'text-gray-600 hover:text-black'}`

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const leave = () => { logout(); navigate('/') }
  return <>
    <header className="border-b border-gray-200">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link to="/" className="font-bold"><span className="mr-2 inline-block h-3 w-3 rounded-sm bg-amber-500" />Ticket Booking System</Link>
        <nav className="flex items-center gap-5">
          <NavLink className={navClass} to="/">Events</NavLink>
          {user?.role === 'customer' && <><NavLink className={navClass} to="/customer">Dashboard</NavLink><NavLink className={navClass} to="/bookings">Bookings</NavLink><NavLink className={navClass} to="/waitlist">Waitlist</NavLink></>}
          {user?.role === 'organiser' && <NavLink className={navClass} to="/organiser">Organiser</NavLink>}
          {user?.role === 'admin' && <NavLink className={navClass} to="/admin">Admin</NavLink>}
          {!user ? <><NavLink className={navClass} to="/login">Login</NavLink><Link className="btn" to="/register">Register</Link></> : <button className="btn-secondary" onClick={leave}>Logout</button>}
        </nav>
      </div>
    </header>
    <main className="mx-auto max-w-6xl px-4 py-8"><Outlet /></main>
  </>
}

