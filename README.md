# Ticket Booking System

A production-oriented booking platform for movies and concerts. Customers browse published events, hold and book seats, receive QR tickets, cancel bookings, and use per-category waitlists. Organisers manage their events and see operational and revenue summaries. Admins manage venues, custom seat categories, and seat layouts.

## Tech stack

- Frontend: React 19, Vite, React Router, Axios, Tailwind CSS
- Backend: Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, JWT, APScheduler
- Data: PostgreSQL 16
- Delivery: FastAPI WebSockets, `qrcode`, `aiosmtplib`

## Features by role

- Customer: event filters, event detail, real-time seat map, timed holds, mock checkout confirmation, booking history/detail, QR ticket, cancellation, waitlist join, and timed offer accept/decline.
- Organiser: create/edit/delete owned events, movie/concert types, per-category prices, publication states, seat/bookings/waitlist summary, and confirmed revenue.
- Admin: venue CRUD, custom category CRUD, grid-based seat layout, category assignment, and inactive layout gaps.

Public registration permits customer and organiser accounts. Admin accounts are provisioned through the seed/deployment process. Every protected backend endpoint checks the JWT and role; frontend guards are only a convenience layer.

## Local setup

Requirements: Python 3.11+, Node.js 20+, Docker, and PostgreSQL (Docker Compose is simplest).

### 1. PostgreSQL

```bash
docker compose up -d postgres
```

The service exposes PostgreSQL on `localhost:5432`, persists data in `ticket_booking_pgdata`, and creates both `tickets` and `tickets_test` on first initialization.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Swagger/OpenAPI is available at `http://localhost:8000/docs`; the health endpoint is `/health`.

Seed logins:

- `admin@example.com` / `Admin123!`
- `organiser@example.com` / `Organiser123!`
- `customer@example.com` / `Customer123!`

Change seed passwords and `SECRET_KEY` outside local development.

### 3. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`.

## Environment configuration

Backend variables are documented in `backend/.env.example`: PostgreSQL URL, JWT secret/expiry, seat-hold and waitlist-offer TTLs, frontend origin, and SMTP credentials. Frontend variables in `frontend/.env.example` define HTTP and WebSocket base URLs. Do not commit populated `.env` files.

When SMTP is unset, complete email content is logged and an `email_logs` record is written. With SMTP configured, confirmation email includes event, venue, date/time, seats, reference, and the generated PNG QR attachment. Waitlist email includes a secure random-token link and expiry.

## Migrations and schema

Run migrations with `cd backend && alembic upgrade head`. Create a later migration with `alembic revision --autogenerate -m "description"`, inspect it, then upgrade. The initial migration creates users; venue/category/seat layout; event prices and per-event `show_seats`; holds/items; bookings/seats; waitlist entries/offers; and email logs. Foreign keys, unique event-seat/position/price constraints, lookup indexes, and PostgreSQL partial unique indexes protect active waitlist memberships and pending offers.

`ShowSeat` is the authoritative state for one physical seat at one event. It is updated to `available`, `held`, or `booked` within the same transaction as its hold, booking, or waitlist offer.

## Hold, concurrency, and waitlist behavior

Hold TTL defaults to ten minutes. Hold creation expires stale holds, locks requested `show_seats` with `SELECT … FOR UPDATE`, validates every state, creates the hold/items, and changes state before commit. Confirmation locks the hold and seats again, validates ownership and future expiry, records price snapshots, and converts the state atomically. Expired holds therefore never block a new hold.

Cancellation locks the booking and seats. For each released category it selects the oldest waiting entry using FIFO ordering and `FOR UPDATE SKIP LOCKED`. The seat stays held by a secure-token offer. APScheduler expires unaccepted offers and immediately assigns the same seat to the next waiter; without another waiter it becomes available. Seat-map changes are broadcast over the event WebSocket, while the frontend also polls as a disconnect fallback.

See [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for the concise design rationale.

## Tests

With the Compose PostgreSQL running:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://tickets:tickets@localhost:5432/tickets_test pytest -q
```

Tests cover authentication, holds, duplicate contention, expiry, confirmation, rejection of expired holds, cancellation, FIFO offers, offer rollover, and revenue.

## Deployment notes

- Frontend (Vercel): set the root directory to `frontend`, build command `npm run build`, output `dist`, and configure both `VITE_*` URLs to the public backend origins.
- Backend (Render/Railway): use Python 3.11+, install `backend/requirements.txt`, run `alembic upgrade head` as a release step, and start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Provision PostgreSQL and set all backend environment variables. Use a persistent disk or object storage if QR images must survive container replacement.
- WebSocket proxying must be enabled. Run one scheduler-owning backend process, or move expiry jobs to a dedicated worker/advisory-locked job when scaling horizontally.
- Serve both applications over HTTPS/WSS, rotate secrets, restrict CORS to the frontend, use managed SMTP, and back up PostgreSQL.

## Known assumptions

- Currency is displayed as INR; prices are stored as currency-agnostic two-decimal numerics.
- Payment is intentionally a “Confirm booking” action, as requested.
- Cancellation refunds and cut-off policies are outside scope.
- An event snapshots active venue seats when created; later layout changes affect new events, not existing ones.
- A cancelled booking can create one FIFO offer per released seat. One active entry receives at most one offered seat.

