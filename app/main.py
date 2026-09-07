import asyncio
import time
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.api.v1.endpoints import router as api_v1_router
from app.services.telemetry import init_telemetry
from app.database.job_store import init_job_table
from app.database.store import init_db
from app.worker.processor import worker_instance

logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Azure Enterprise FDE Platform Services...")
    init_db()
    init_job_table()
    init_telemetry()

    if settings.ENABLE_ASYNC_WORKER:
        worker_instance.start_background()
        logger.info("Background Azure Service Bus Worker engine started.")

    yield

    # Shutdown
    logger.info("Shutting down Azure Enterprise FDE Platform Services...")
    if settings.ENABLE_ASYNC_WORKER:
        worker_instance.stop()

app = FastAPI(
    title=f"{settings.PROJECT_NAME} (FDE Azure Production)",
    version=settings.VERSION,
    description="Enterprise Forward Deployed Engineering (FDE) Multimodal AI Platform powered by Azure AI Document Intelligence, Azure OpenAI Vision, Azure Service Bus, and Application Insights.",
    lifespan=lifespan
)

# Start worker on module load if enabled
if settings.ENABLE_ASYNC_WORKER and not worker_instance._running:
    worker_instance.start_background()

# Concurrency limiting semaphore (Limit up to 10 concurrent heavy tasks at once)
CONCURRENCY_SEMAPHORE = asyncio.Semaphore(settings.MAX_CONCURRENT_USERS)

@app.middleware("http")
async def concurrency_limit_middleware(request: Request, call_next):
    # Apply concurrency limiter on CPU/IO-heavy document processing routes
    if request.url.path.startswith("/api/v1/documents/upload") or request.url.path.startswith("/api/v1/documents/url"):
        try:
            await asyncio.wait_for(CONCURRENCY_SEMAPHORE.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"System concurrency limit reached ({settings.MAX_CONCURRENT_USERS} active processing slots). Please retry in a moment."
                }
            )
        try:
            response = await call_next(request)
            return response
        finally:
            CONCURRENCY_SEMAPHORE.release()
    else:
        return await call_next(request)

# Configure CORS for multi-tenant and frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Mount static web directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_index():
    """Serves the main dual-pane interactive dashboard web application."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Welcome to {settings.PROJECT_NAME}. API documentation available at /docs."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
