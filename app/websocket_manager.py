
import asyncio
import json
import threading
from typing import Optional
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Call this on app startup to register the event loop."""
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._lock:
            self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Send a message to all connected clients. Dead connections are pruned."""
        payload = json.dumps(message)
        dead = []
        with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        with self._lock:
            for ws in dead:
                if ws in self._connections:
                    self._connections.remove(ws)

    def broadcast_from_thread(self, message: dict):
        """
        Thread-safe broadcast. Call this from reader threads or
        race tracker callbacks that run outside the async event loop.
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast(message),
                self._loop,
            )

    def broadcast_gate_event(self, event: dict):
        """Convenience wrapper for gate event broadcasts."""
        self.broadcast_from_thread({
            "type": "gate_event",
            "data": event,
        })

    def connection_count(self) -> int:
        with self._lock:
            return len(self._connections)


# Singleton
ws_manager = WebSocketManager()
