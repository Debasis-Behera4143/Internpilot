"""FastAPI application entrypoint for AI-Powered Student Career & Opportunity Hub."""

import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.utils.config import settings
from backend.utils.security import hash_password
from backend.database.db import SessionLocal, UserDB
from backend.database.sync import sync_json_to_db
from backend.api.routes_auth import router as auth_router
from backend.api.routes_admin import router as admin_router
from backend.api.routes_opportunities import router as opps_router
from backend.api.routes_students import router as student_router, plural_router as students_router
from backend.api.routes_matching import router as matching_router
from backend.api.routes_tracker import router as tracker_router


from backend.services.scheduler_service import start_background_scheduler, stop_background_scheduler


def init_default_admin():
    """Create default admin user if configured in environment variables."""
    if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
        session = SessionLocal()
        try:
            admin_email = settings.ADMIN_EMAIL.strip().lower()
            existing = session.query(UserDB).filter(UserDB.email == admin_email).first()
            if not existing:
                admin_user = UserDB(
                    id=f"usr_{uuid.uuid4().hex[:12]}",
                    email=admin_email,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    role="ADMIN",
                    is_active=True,
                )
                session.add(admin_user)
                session.commit()
        finally:
            session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema exists, initial admin is seeded if configured, syncs with JSON, and runs background ingestion."""
    init_default_admin()
    sync_json_to_db()
    start_background_scheduler()
    try:
        yield
    finally:
        stop_background_scheduler()


app = FastAPI(
    title="AI-Powered Student Career & Opportunity Hub",
    description="Intelligent platform aggregating, matching, ranking, and tracking student internship and career opportunities.",
    version="1.0.0",
    lifespan=lifespan,
)

# Include Security Headers & Rate Limiting Middleware
from backend.api.middleware import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS for local development and web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(opps_router)
app.include_router(student_router)
app.include_router(students_router)
app.include_router(matching_router)
app.include_router(tracker_router)


@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "embedding_model": settings.EMBEDDING_MODEL,
    }


# Mount frontend static directory if exists
frontend_dir = settings.ROOT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend_index():
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": f"Welcome to {settings.APP_NAME} API. Visit /docs for Swagger UI."}
