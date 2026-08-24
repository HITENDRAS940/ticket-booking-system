import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { errorMessage, WS_BASE } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import SeatMap from '../components/SeatMap'

export default function EventDetailPage() {
  const { eventId } = useParams(); const navigate = useNavigate(); const { user } = useAuth()
  const [event, setEvent] = useState(null); const [map, setMap] = useState(null); const [selected, setSelected] = useState([])
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  const load = useCallback(async () => {
    try { const [e, m] = await Promise.all([api.get(`/api/events/${eventId}`), api.get(`/api/events/${eventId}/seat-map`)]); setEvent(e.data); setMap(m.data); setSelected((old) => old.filter((id) => m.data.seats.find((s) => s.id === id)?.status === 'available')) } catch (err) { setError(errorMessage(err)) }
  }, [eventId])
  useEffect(() => { load(); const socket = new WebSocket(`${WS_BASE}/ws/events/${eventId}/seat-map`); socket.onmessage = load; const fallback = setInterval(load, 30000); return () => { socket.close(); clearInterval(fallback) } }, [eventId, load])
  const total = useMemo(() => map?.seats.filter((s) => selected.includes(s.id)).reduce((sum, s) => sum + Number(s.price), 0) || 0, [map, selected])
  const toggle = (seat) => setSelected((current) => current.includes(seat.id) ? current.filter((id) => id !== seat.id) : [...current, seat.id])
  const hold = async () => {
    if (user?.role !== 'customer') return navigate('/login', { state: { from: { pathname: `/events/${eventId}` } } })
    setBusy(true); setError('')
    try { const { data } = await api.post(`/api/events/${eventId}/holds`, { show_seat_ids: selected }); navigate(`/checkout/${data.id}`) } catch (err) { setError(errorMessage(err)); load() } finally { setBusy(false) }
  }
  const join = async (categoryId) => { try { await api.post(`/api/events/${eventId}/waitlist`, { category_id: categoryId }); navigate('/waitlist') } catch (err) { setError(errorMessage(err)) } }
  if (!event || !map) return <p>{error || 'Loading event…'}</p>
  const categories = event.prices.map((price) => ({...price, available: map.seats.some((s) => s.category_id === price.category_id && s.status === 'available')}))
  return <div>
    <Link className="text-sm text-gray-600 hover:text-black" to="/">← Events</Link>
    <div className="mt-4 grid gap-8 lg:grid-cols-[1fr_300px]">
      <section><h1 className="page-title">{event.title}</h1><p className="mt-2 text-sm text-gray-600">{event.venue.name} · {event.show_date} at {event.show_time.slice(0, 5)}</p><p className="mt-4 max-w-3xl text-sm leading-6">{event.description}</p>
        <div className="mt-8 panel"><SeatMap data={map} selected={selected} onToggle={toggle} /></div>
      </section>
      <aside className="space-y-4"><div className="panel"><h2 className="font-semibold">Seat key</h2><div className="mt-3 space-y-2 text-sm"><p><span className="mr-2 inline-block h-4 w-4 rounded border border-gray-400 bg-white" />Available</p><p><span className="mr-2 inline-block h-4 w-4 rounded bg-amber-500" />Selected</p><p><span className="mr-2 inline-block h-4 w-4 rounded bg-gray-200" />Held or booked</p></div></div>
        <div className="panel"><h2 className="font-semibold">Categories</h2>{categories.map((c) => <div key={c.category_id} className="mt-3 flex items-center justify-between text-sm"><span>{c.category_name} · ₹{c.price}</span>{!c.available && user?.role === 'customer' && <button className="text-amber-700 underline" onClick={() => join(c.category_id)}>Join waitlist</button>}</div>)}</div>
        <div className="panel"><div className="flex justify-between text-sm"><span>{selected.length} selected</span><strong>₹{total.toFixed(2)}</strong></div>{error && <p className="error mt-3">{error}</p>}<button onClick={hold} disabled={!selected.length || busy} className="btn mt-4 w-full">{busy ? 'Holding…' : 'Hold seats'}</button></div>
      </aside>
    </div>
  </div>
}

