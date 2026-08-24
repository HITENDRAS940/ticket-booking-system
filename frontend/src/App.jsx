import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './routes/ProtectedRoute'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import EventsPage from './pages/EventsPage'
import EventDetailPage from './pages/EventDetailPage'
import { BookingDetailPage, BookingsPage, CheckoutPage, CustomerDashboard, OfferPage, WaitlistPage } from './pages/CustomerPages'
import { AdminDashboard, SeatLayoutPage, VenueFormPage } from './pages/AdminPages'
import { EventFormPage, EventSummaryPage, OrganiserDashboard } from './pages/OrganiserPages'

const Guard = ({ roles, children }) => <ProtectedRoute roles={roles}>{children}</ProtectedRoute>

export default function App() {
  return <Routes><Route element={<Layout />}>
    <Route index element={<EventsPage />} />
    <Route path="events/:eventId" element={<EventDetailPage />} />
    <Route path="login" element={<LoginPage />} />
    <Route path="register" element={<RegisterPage />} />
    <Route path="customer" element={<Guard roles={['customer']}><CustomerDashboard /></Guard>} />
    <Route path="checkout/:holdId" element={<Guard roles={['customer']}><CheckoutPage /></Guard>} />
    <Route path="bookings" element={<Guard roles={['customer']}><BookingsPage /></Guard>} />
    <Route path="bookings/:bookingId" element={<Guard roles={['customer']}><BookingDetailPage /></Guard>} />
    <Route path="waitlist" element={<Guard roles={['customer']}><WaitlistPage /></Guard>} />
    <Route path="offers/:token" element={<Guard roles={['customer']}><OfferPage /></Guard>} />
    <Route path="organiser" element={<Guard roles={['organiser']}><OrganiserDashboard /></Guard>} />
    <Route path="organiser/events/new" element={<Guard roles={['organiser']}><EventFormPage /></Guard>} />
    <Route path="organiser/events/:eventId/edit" element={<Guard roles={['organiser']}><EventFormPage /></Guard>} />
    <Route path="organiser/events/:eventId/summary" element={<Guard roles={['organiser']}><EventSummaryPage /></Guard>} />
    <Route path="admin" element={<Guard roles={['admin']}><AdminDashboard /></Guard>} />
    <Route path="admin/venues/new" element={<Guard roles={['admin']}><VenueFormPage /></Guard>} />
    <Route path="admin/venues/:venueId/edit" element={<Guard roles={['admin']}><VenueFormPage /></Guard>} />
    <Route path="admin/venues/:venueId/layout" element={<Guard roles={['admin']}><SeatLayoutPage /></Guard>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes>
}

