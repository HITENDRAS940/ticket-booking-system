# System Design

## Seat map model

`Seat` represents a physical venue position and category. `ShowSeat` snapshots each active venue seat when an event is created and is the authoritative event-specific state: `available`, `held`, or `booked`. `EventCategoryPrice` supplies the live category price; `BookingSeat.price` stores the immutable price paid. Inactive venue positions are omitted from new event maps, supporting aisles and layout gaps.

## Seat holds and TTL

Proceeding from selection creates one `SeatHold` plus `SeatHoldItem` rows. Its expiry is calculated from `SEAT_HOLD_TTL_MINUTES` (ten minutes by default). `ShowSeat.current_hold_id` links the visible held state to its owner. APScheduler periodically marks overdue holds expired, clears matching links, releases their seats, and broadcasts the change. Hold creation also expires stale holds for that event before validation, so scheduler delay cannot make an expired hold block a seat.

Checkout locks the hold and seats, verifies user ownership, active status, future expiry, and matching seat links, then creates the booking and price snapshots in the same transaction. The hold becomes converted and each seat becomes booked. A late confirmation is rejected and its stale hold is released.

## Concurrency prevention

All state transitions run in PostgreSQL transactions. Requested `ShowSeat` rows are selected in stable ID order using `SELECT FOR UPDATE`. A competing hold or confirmation waits, then observes the committed non-available state and fails with a conflict. Confirmation and cancellation also lock their parent record and all affected seats. Unique constraints protect physical seat positions, event-seat snapshots, category prices, booking references, and membership rows. Partial unique PostgreSQL indexes allow only one active (`waiting`/`offered`) waitlist entry per user/event/category and one pending offer per seat.

## Waitlist assignment and offers

Waitlists are scoped to event and category. A customer may join only when no seat in that category is available. Cancellation locks booked seats and, per released seat, selects the oldest `waiting` entry using `created_at, id FOR UPDATE SKIP LOCKED`. It creates a cryptographically random-token `WaitlistOffer`, changes the entry to `offered`, and keeps the seat `held`; the seat never leaks into general inventory.

Offer links expire according to `WAITLIST_OFFER_TTL_MINUTES`. Acceptance locks the offer and seat, validates token ownership/status/expiry, creates a one-seat booking at the configured price, marks the entry fulfilled, and books the seat. Decline or scheduled expiry marks the current offer and entry terminal, then atomically repeats FIFO assignment for the next waiter. If none remains, the seat becomes available.

## Real-time updates

FastAPI keeps WebSocket subscribers grouped by event. Successful hold, release, confirmation, cancellation, offer reservation/reassignment, and scheduled expiry broadcast affected `ShowSeat` IDs after commit. Clients refresh the authoritative REST seat map on every message. A 30-second REST fallback keeps maps current after a failed WebSocket connection.

## QR and email flow

After transaction commit, the backend generates a PNG QR whose content is the unique booking reference and records its static path. It sends an HTML confirmation containing customer, event, venue, schedule, seats, and reference, with the QR attached. Offer email contains category, expiry, and the frontend token link. SMTP credentials come only from environment variables. When SMTP is absent, development logs contain the email body and `EmailLog` records delivery state. Email failure is logged and never rolls back a confirmed booking.

