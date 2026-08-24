from collections import defaultdict

from fastapi import WebSocket


class SeatMapConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, event_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[event_id].add(websocket)

    def disconnect(self, event_id: int, websocket: WebSocket):
        self.connections[event_id].discard(websocket)

    async def broadcast(self, event_id: int, action: str, seat_ids: list[int]):
        dead = []
        for socket in list(self.connections[event_id]):
            try:
                await socket.send_json({"type": "seat-map-update", "action": action, "show_seat_ids": seat_ids})
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(event_id, socket)


manager = SeatMapConnectionManager()

