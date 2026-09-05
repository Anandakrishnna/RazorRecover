import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.db.session import init_db
from backend.api.routes import events, cases, metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database & tables exist
    init_db()
    yield

app = FastAPI(
    title="RazorRecover API",
    description="Autonomous Revenue Recovery Agent API — Razorpay AI Buildathon",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React/Next.js dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(events.router)
app.include_router(cases.router)
app.include_router(metrics.router)

@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "system": "RazorRecover Autonomous Agent API",
        "status": "HEALTHY",
        "version": "1.0.0"
    }

# Mount static frontend directory if it exists (for single-container production hosting)
frontend_dist = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dashboard", "dist")
)

if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str, request: Request):
        if full_path == "" and "application/json" in request.headers.get("accept", ""):
            return health_check()
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return health_check()
else:
    @app.get("/", tags=["Health"])
    def root_health():
        return health_check()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=port, reload=True)

