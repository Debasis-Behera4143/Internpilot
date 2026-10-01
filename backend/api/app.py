"""FastAPI application entrypoint for AI-Powered Student Career & Opportunity Hub."""

import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.utils.config import settings
from backend.utils.security import hash_password
from backend.database.db import SessionLocal, UserDB, get_db
from backend.database.sync import sync_json_to_db
from backend.api.routes_auth import router as auth_router
from backend.api.routes_admin import router as admin_router
from backend.api.routes_opportunities import router as opps_router
from backend.api.routes_students import router as student_router, plural_router as students_router
from backend.api.routes_matching import router as matching_router
from backend.api.routes_tracker import router as tracker_router


from backend.services.scheduler_service import start_background_scheduler, stop_background_scheduler


from backend.utils.logger import get_logger
logger = get_logger("app")

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
                logger.info(f"[STARTUP] Initial admin account created for: {admin_email}")
        except Exception as e:
            logger.error(f"[STARTUP] Could not initialize default admin: {e}")
        finally:
            session.close()


async def _async_background_data_sync():
    """Run JSON to DB sync asynchronously so it never delays web server readiness."""
    import asyncio
    try:
        logger.info("[BACKGROUND] Starting JSON-to-DB database synchronization...")
        await asyncio.to_thread(sync_json_to_db)
        logger.info("[BACKGROUND] Database synchronization completed.")
    except Exception as e:
        logger.error(f"[BACKGROUND] Error in background data synchronization: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure fast startup: minimal database init, immediate yield for health check, and async background operations."""
    import asyncio
    logger.info("[STARTUP] FastAPI application initializing...")
    
    # 1. Lightweight DB & admin check
    try:
        from backend.database.db import init_db
        init_db()
        logger.info("[STARTUP] Database schema ready.")
        init_default_admin()
    except Exception as e:
        logger.error(f"[STARTUP] Error during minimal database setup: {e}", exc_info=True)

    # 2. Start non-blocking background tasks
    asyncio.create_task(_async_background_data_sync())
    start_background_scheduler()
    logger.info("[STARTUP] Application ready. Yielding for HTTP traffic.")

    try:
        yield
    finally:
        logger.info("[SHUTDOWN] Application shutting down...")
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

# Enable CORS safely:
# For production same-origin serving and local development without wildcard credentials violation
cors_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "https://internpilot-jl6l.onrender.com",
]
if settings.APP_ENV == "development" or settings.DEBUG:
    cors_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if "*" not in cors_origins else ["*"],
    allow_credentials=True if "*" not in cors_origins else False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
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
    """Immediate, non-blocking health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
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

    @app.get("/admin", include_in_schema=False)
    def serve_admin_portal(
        request: Request,
        db: Session = Depends(get_db)
    ):
        """Enforce backend authentication and authorization for /admin access."""
        from backend.api.deps import get_current_user_optional
        user = get_current_user_optional(request, token=None, db=db)
        
        # If unauthenticated, redirect to login page with clear feedback or reject
        accept_header = request.headers.get("accept", "")
        if not user:
            if "text/html" in accept_header:
                return RedirectResponse(url="/?auth=login&redirect=/admin&error=unauthorized", status_code=302)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access admin portal",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # If authenticated but not an ADMIN, return 403 Forbidden immediately
        if user.role != "ADMIN":
            if "text/html" in accept_header:
                # Return standard 403 response
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Admin privileges required to access this resource"
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Admin privileges required"
            )

        # Authorized Admin: serve the application with admin context
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Admin portal authorized."}

