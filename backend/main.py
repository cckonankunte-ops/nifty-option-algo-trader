"""FastAPI application entry point — wires all components together."""

import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import Base, engine
from backend.websocket_manager import ws_manager
from backend.routers import trading, backtest, config, history, settings as settings_router

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
log_handler = RotatingFileHandler("logs/app.log", maxBytes=10_000_000, backupCount=5)
log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.basicConfig(level=settings.LOG_LEVEL, handlers=[log_handler, logging.StreamHandler()])

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    Base.metadata.create_all(bind=engine)
    logger.info(f"App started — mode: {settings.TRADING_MODE}, env: {settings.ENVIRONMENT}")
    yield
    # Shutdown
    logger.info("App shutting down")


app = FastAPI(
    title="Nifty Options Algo Trader",
    description="Automated algo trading for Nifty Options (Buy Call / Buy Put)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(trading.router)
app.include_router(backtest.router)
app.include_router(config.router)
app.include_router(history.router)
app.include_router(settings_router.router)


# WebSocket endpoint
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "trading_mode": settings.TRADING_MODE,
        "ws_clients": ws_manager.client_count,
    }
