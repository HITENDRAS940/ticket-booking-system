from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, bookings, events, organiser, waitlist
from app.core.config import settings
from app.tasks.expiry import run_expiry_cycle
from app.websocket.manager import manager

@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_expiry_cycle, "interval", seconds=settings.scheduler_interval_seconds, max_instances=1, coalesce=True)
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(organiser.router)
app.include_router(events.router)
app.include_router(bookings.router)
app.include_router(waitlist.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws/events/{event_id}/seat-map")
async def event_seat_map(websocket: WebSocket, event_id: int):
    await manager.connect(event_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(event_id, websocket)
