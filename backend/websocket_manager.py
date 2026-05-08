"""WebSocket Manager — broadcasts real-time events to connected frontend clients."""

import json
import logging
from datetime import datetime
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events."""

    # Supported event types
    EVENT_TYPES = [
        "TICK",
        "SIGNAL",
        "ORDER_PLACED",
        "ORDER_FILLED",
        "SL_HIT",
        "TRAILING_SL_UPDATE",
        "DAILY_CAP_HIT",
        "ENGINE_STATUS",
        "ERROR",
    ]

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket client."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected client."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event_type: str, payload: Any = None):
        """
        Broadcast a structured event to all connected clients.

        Args:
            event_type: One of EVENT_TYPES
            payload: Event-specific data
        """
        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }

        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)


# Singleton instance
ws_manager = WebSocketManager()
