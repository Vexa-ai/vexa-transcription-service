"""Run FastAPI server."""
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.api import router
from app.events import add_event_handlers
from app.exception_handler import add_exception_handlers
from app.settings import settings

app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
)

add_exception_handlers(app)
add_event_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://*", "https://*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.service_api_host, port=settings.service_api_port)
