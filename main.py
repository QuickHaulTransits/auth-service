import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
import sys
from pathlib import Path

# Add backend root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.database import connect_to_db, close_db
from shared.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .api import router

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Auth Service starting up...")
    await connect_to_db()
    yield
    logger.info("Auth Service shutting down...")
    await close_db()

app = FastAPI(
    title="Auth Service",
    description="Authentication and authorization microservice",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/auth")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}

if __name__ == "__main__":
    uvicorn.run("services.auth_service.main:app", host="127.0.0.1", port=8001, reload=True)
