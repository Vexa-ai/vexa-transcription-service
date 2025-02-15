"""Run FastAPI server."""
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from streamqueue.api.api import router
from streamqueue.settings import settings

def create_app() -> FastAPI:
    app = FastAPI(
        title='StreamQueue',
        version='0.1.0',
        debug=True
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://*", "https://*", "chrome-extension://*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",  # Changed from app to "main:app"
        host="0.0.0.0",  # Allow external connections
        port=settings.api_port,
        reload=True  # Enable auto-reload for development
    )
