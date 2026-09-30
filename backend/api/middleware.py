"""Security middleware: HTTP security headers, request size limits, and in-memory rate limiting."""

import time
from typing import Dict, Tuple
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

# In-memory token bucket for rate limiting: ip -> (tokens, last_update_time)
_rate_limit_state: Dict[str, Tuple[float, float]] = {}

# Strict paths requiring rate limiting
RATE_LIMITED_PATHS = {
    "/api/auth/login": (10, 1.0),       # 10 requests max, refilled 1/sec
    "/api/auth/register": (5, 0.2),      # 5 requests max, refilled 1 every 5 sec
    "/api/admin/sources": (30, 2.0),     # 30 requests max
    "/api/student/resume": (10, 0.5),    # 10 resume uploads
}

# Max allowed request body size: 10MB
MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects robust OWASP-recommended security headers into every HTTP response."""

    async def dispatch(self, request: Request, call_next):
        # 1. Check content length to protect against oversized payload attacks
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_SIZE:
                    return Response(
                        content='{"detail": "Request payload exceeds maximum allowed size limit (10MB)."}',
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        media_type="application/json"
                    )
            except ValueError:
                pass

        # 2. Rate limiting check on sensitive endpoints
        client_ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path

        for rule_path, (max_tokens, refill_rate) in RATE_LIMITED_PATHS.items():
            if path.startswith(rule_path):
                key = f"{client_ip}:{rule_path}"
                now = time.time()
                tokens, last_time = _rate_limit_state.get(key, (float(max_tokens), now))

                # Refill tokens
                elapsed = now - last_time
                tokens = min(float(max_tokens), tokens + elapsed * refill_rate)

                if tokens < 1.0:
                    return Response(
                        content='{"detail": "Too many requests. Please slow down and try again shortly."}',
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        media_type="application/json",
                        headers={"Retry-After": "5"}
                    )

                _rate_limit_state[key] = (tokens - 1.0, now)
                break

        response = await call_next(request)

        # 3. Inject Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # CSP compatible with FastAPI Swagger UI & vanilla frontend
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https:;"
        )

        return response
