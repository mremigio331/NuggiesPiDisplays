from fastapi import WebSocket


class ClockWSManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket, current_settings: dict):
        await ws.accept()
        self._clients.add(ws)
        await ws.send_json(current_settings)

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def broadcast(self, data: dict):
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead


manager = ClockWSManager()
