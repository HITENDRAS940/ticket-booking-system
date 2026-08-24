import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { API_BASE, errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import StatusBadge from '../components/StatusBadge'

export function CustomerDashboard() {
  const { user } = useAuth(); const [bookings, setBookings] = useState([]); const [waitlist, setWaitlist] = useState([])
  useEffect(() => { Promise.all([api.get('/api/bookings/my'), api.get('/api/waitlist/my')]).then(([a, b]) => { setBookings(a.data); setWaitlist(b.data) }) }, [])
  return <div><h1 className="page-title">Welcome, {user.name}</h1><div className="mt-6 grid gap-4 sm:grid-cols-3"><div className="panel"><p className="text-sm text-gray-500">Confirmed bookings</p><p className="mt-1 text-2xl font-bold">{bookings.filter((b) => b.status === 'confirmed').length}</p></div><div className="panel"><p className="text-sm text-gray-500">Active waitlists</p><p className="mt-1 text-2xl font-bold">{waitlist.filter((w) => ['waiting','offered'].includes(w.status)).length}</p></div><div className="panel flex items-center"><Link className="btn w-full" to="/">Browse events</Link></div></div></div>
}

export function CheckoutPage() {
  const { holdId } = useParams(); const navigate = useNavigate(); const { user } = useAuth()
  const [hold, setHold] = useState(null); const [seconds, setSeconds] = useState(0); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { api.get(`/api/holds/${holdId}`).then((r) => setHold(r.data)).catch((e) => setError(errorMessage(e))) }, [holdId])
  useEffect(() => { if (!hold) return; const tick = () => setSeconds(Math.max(0, Math.floor((new Date(hold.expires_at) - Date.now()) / 1000))); tick(); const id = setInterval(tick, 1000); return () => clearInterval(id) }, [hold])
  const confirm = async () => { setBusy(true); try { const { data } = await api.post('/api/bookings/confirm', { hold_id: Number(holdId), customer_name: user.name, customer_email: user.email }); navigate(`/bookings/${data.id}`) } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  const release = async () => { try { await api.delete(`/api/holds/${holdId}`); navigate(`/events/${hold.event_id}`) } catch (e) { setError(errorMessage(e)) } }
  if (!hold) return <p>{error || 'Loading checkout…'}</p>
  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
  return <div className="mx-auto max-w-xl"><h1 className="page-title">Confirm your booking</h1><div className="panel mt-6 space-y-5"><div className="rounded-md bg-amber-50 p-3 text-sm"><strong>Seats held for {clock}</strong><p className="mt-1 text-gray-700">Complete before the timer reaches zero.</p></div><div><label>Name</label><input value={user.name} readOnly /></div><div><label>Email</label><input value={user.email} readOnly /></div><p className="text-sm">Seats selected: <strong>{hold.show_seat_ids.length}</strong></p>{error && <p className="error">{error}</p>}<div className="flex gap-3"><button className="btn flex-1" disabled={!seconds || busy} onClick={confirm}>{busy ? 'Confirming…' : 'Confirm booking'}</button><button className="btn-secondary" onClick={release}>Release seats</button></div></div></div>
}

export function BookingsPage() {
  const [items, setItems] = useState([]); const [error, setError] = useState('')
  const load = useCallback(() => api.get('/api/bookings/my').then((r) => setItems(r.data)).catch((e) => setError(errorMessage(e))), [])
  useEffect(load, [load])
  return <div><h1 className="page-title mb-6">Booking history</h1>{error && <p className="error">{error}</p>}<div className="overflow-x-auto border border-gray-200"><table><thead><tr><th>Reference</th><th>Event</th><th>Date</th><th>Seats</th><th>Total</th><th>Status</th><th /></tr></thead><tbody>{items.map((b) => <tr key={b.id}><td className="font-mono">{b.booking_reference}</td><td>{b.event_title}</td><td>{b.show_date}</td><td>{b.seats.map((s) => s.label).join(', ')}</td><td>₹{b.total_amount}</td><td><StatusBadge value={b.status} /></td><td><Link className="text-amber-700 underline" to={`/bookings/${b.id}`}>View</Link></td></tr>)}</tbody></table>{!items.length && <p className="p-6 text-center text-sm text-gray-500">No bookings yet.</p>}</div></div>
}

export function BookingDetailPage() {
  const { bookingId } = useParams(); const [booking, setBooking] = useState(null); const [error, setError] = useState('')
  const load = useCallback(() => api.get(`/api/bookings/${bookingId}`).then((r) => setBooking(r.data)).catch((e) => setError(errorMessage(e))), [bookingId])
  useEffect(load, [load])
  const cancel = async () => { if (!window.confirm('Cancel this booking? The seats may be offered to the waitlist.')) return; try { await api.post(`/api/bookings/${bookingId}/cancel`); load() } catch (e) { setError(errorMessage(e)) } }
  if (!booking) return <p>{error || 'Loading booking…'}</p>
  return <div className="mx-auto max-w-2xl"><Link className="text-sm text-gray-600" to="/bookings">← Booking history</Link><div className="panel mt-4"><div className="flex items-start justify-between"><div><h1 className="page-title">{booking.event_title}</h1><p className="mt-2 font-mono text-sm">{booking.booking_reference}</p></div><StatusBadge value={booking.status} /></div><dl className="mt-6 grid gap-4 text-sm sm:grid-cols-2"><div><dt className="text-gray-500">Venue</dt><dd>{booking.venue_name}</dd></div><div><dt className="text-gray-500">Date and time</dt><dd>{booking.show_date} · {booking.show_time.slice(0, 5)}</dd></div><div><dt className="text-gray-500">Seats</dt><dd>{booking.seats.map((s) => s.label).join(', ')}</dd></div><div><dt className="text-gray-500">Total</dt><dd>₹{booking.total_amount}</dd></div></dl>{booking.qr_code_path && <div className="mt-6 border-t pt-5"><p className="mb-2 text-sm font-medium">Entry QR code</p><img className="h-40 w-40" src={`${API_BASE}${booking.qr_code_path}`} alt={`QR code for ${booking.booking_reference}`} /></div>}{error && <p className="error mt-4">{error}</p>}{booking.status === 'confirmed' && <button className="btn-danger mt-6" onClick={cancel}>Cancel booking</button>}</div></div>
}

export function WaitlistPage() {
  const [items, setItems] = useState([]); const [error, setError] = useState('')
  useEffect(() => { api.get('/api/waitlist/my').then((r) => setItems(r.data)).catch((e) => setError(errorMessage(e))) }, [])
  return <div><h1 className="page-title mb-6">My waitlists</h1>{error && <p className="error mb-4">{error}</p>}<div className="space-y-3">{items.map((item) => <div className="panel flex items-center justify-between" key={item.id}><div><h2 className="font-semibold">{item.event_title}</h2><p className="mt-1 text-sm text-gray-600">{item.category_name} · joined {new Date(item.created_at).toLocaleString()}</p></div><div className="flex items-center gap-3"><StatusBadge value={item.status} />{item.offer?.status === 'pending' && <Link className="btn" to={`/offers/${item.offer.token}`}>View offer</Link>}</div></div>)}{!items.length && <p className="panel text-center text-sm text-gray-500">You have not joined a waitlist.</p>}</div></div>
}

export function OfferPage() {
  const { token } = useParams(); const navigate = useNavigate(); const [offer, setOffer] = useState(null); const [error, setError] = useState('')
  useEffect(() => { api.get(`/api/waitlist/offers/${token}`).then((r) => setOffer(r.data)).catch((e) => setError(errorMessage(e))) }, [token])
  const action = async (kind) => { try { const { data } = await api.post(`/api/waitlist/offers/${token}/${kind}`); navigate(kind === 'accept' ? `/bookings/${data.booking_id}` : '/waitlist') } catch (e) { setError(errorMessage(e)) } }
  if (!offer) return <p>{error || 'Loading offer…'}</p>
  return <div className="mx-auto max-w-lg"><h1 className="page-title">Waitlist offer</h1><div className="panel mt-6"><h2 className="text-lg font-semibold">{offer.event_title}</h2><p className="mt-2 text-sm">Category: {offer.category_name}</p><p className="mt-1 text-sm">Reserved until: {new Date(offer.expires_at).toLocaleString()}</p><div className="mt-3"><StatusBadge value={offer.status} /></div>{error && <p className="error mt-4">{error}</p>}{offer.status === 'pending' && <div className="mt-6 flex gap-3"><button className="btn flex-1" onClick={() => action('accept')}>Accept offer</button><button className="btn-secondary flex-1" onClick={() => action('decline')}>Decline offer</button></div>}</div></div>
}

