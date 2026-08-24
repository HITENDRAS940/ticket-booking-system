import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { errorMessage } from '../api/client'

export default function EventsPage() {
  const [events, setEvents] = useState([])
  const [filters, setFilters] = useState({ search: '', event_type: '', show_date: '', venue_id: '', availability: '' })
  const [error, setError] = useState('')
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''))
    api.get('/api/events', { params }).then((r) => setEvents(r.data)).catch((e) => setError(errorMessage(e)))
  }, [filters])
  return <div>
    <div className="mb-6"><h1 className="page-title">Movies and concerts</h1><p className="mt-1 text-sm text-gray-600">Choose an event, then select your seats.</p></div>
    <div className="mb-6 grid gap-3 rounded-lg border border-gray-200 p-4 md:grid-cols-5">
      <input aria-label="Search" placeholder="Search events" value={filters.search} onChange={(e) => setFilters({...filters, search: e.target.value})} />
      <select aria-label="Event type" value={filters.event_type} onChange={(e) => setFilters({...filters, event_type: e.target.value})}><option value="">All types</option><option value="movie">Movies</option><option value="concert">Concerts</option></select>
      <input aria-label="Date" type="date" value={filters.show_date} onChange={(e) => setFilters({...filters, show_date: e.target.value})} />
      <input aria-label="Venue ID" type="number" placeholder="Venue ID" value={filters.venue_id} onChange={(e) => setFilters({...filters, venue_id: e.target.value})} />
      <select aria-label="Availability" value={filters.availability} onChange={(e) => setFilters({...filters, availability: e.target.value})}><option value="">Any availability</option><option value="true">Available</option><option value="false">Sold out</option></select>
    </div>
    {error && <p className="error mb-4">{error}</p>}
    <div className="divide-y divide-gray-200 border-y border-gray-200">
      {events.map((event) => <article key={event.id} className="grid gap-3 py-5 md:grid-cols-[1fr_auto] md:items-center">
        <div><div className="mb-1 flex items-center gap-2"><h2 className="text-lg font-semibold">{event.title}</h2><span className="rounded border border-gray-200 px-2 py-0.5 text-xs capitalize">{event.event_type}</span></div>
          <p className="text-sm text-gray-600">{event.venue.name} · {event.show_date} at {event.show_time.slice(0, 5)}</p>
          <p className="mt-2 line-clamp-2 text-sm text-gray-700">{event.description}</p>
          <p className="mt-2 text-sm font-medium">{event.available_seats ? `${event.available_seats} seats available` : 'Sold out — waitlist available'}</p>
        </div><Link className="btn" to={`/events/${event.id}`}>View seats</Link>
      </article>)}
      {!events.length && !error && <p className="py-10 text-center text-sm text-gray-500">No events match these filters.</p>}
    </div>
  </div>
}

