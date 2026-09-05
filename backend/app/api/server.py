"""
Project Vulcan: FastAPI Server Assembly
Author: Alex Xu & Uncle Bob
Configures lifespan, CORS middleware, WebSocket loop binding, and route registry.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.websockets import ws_hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set the running event loop on the WebSocket hub for thread-safe worker broadcasts
    loop = asyncio.get_running_loop()
    ws_hub.set_event_loop(loop)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Project Vulcan: Enterprise Automation Control Plane",
        description="High-reliability banking automation platform OS (PNC Bank Standard)",
        version="1.0.0",
        lifespan=lifespan
    )

    # Allow cross-origin requests from Jordan Walke's Next.js 15 Obsidian Glass frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
