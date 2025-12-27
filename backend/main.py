from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import files, jobs
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="Cloud Service Spark Platform")

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"🔵 Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"✅ Response: {response.status_code} | Duration: {duration:.2f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Error: {str(e)} | Duration: {duration:.2f}s")
        raise

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(jobs.router)

@app.get("/")
def read_root():
    return {"message": "Cloud Service API is running"}

@app.on_event("startup")
def startup_event():
    logger.info("🚀 Cloud Service API started")
    logger.info("📋 Available routes:")
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            logger.info(f"  {', '.join(route.methods)} {route.path}")
