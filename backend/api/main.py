import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.session import init_db
from backend.api.routes import events, cases, metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database & tables exist
    init_db()
    yield
    # Shutdown logic (if any)

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

@app.get("/", tags=["Health"])
def health_check():
    return {
        "system": "RazorRecover Autonomous Agent API",
        "status": "HEALTHY",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
