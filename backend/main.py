"""
Project Vulcan: Enterprise Automation Control Plane Main Entrypoint
"""
import os
import uvicorn
from app.api.server import app

if __name__ == "__main__":
    workers = int(os.getenv("UVICORN_WORKERS", "1"))
    reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true" if workers == 1 else False
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=reload, workers=workers if not reload else None)
