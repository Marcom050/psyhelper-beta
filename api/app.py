"""FastAPI application exposing the minimal PsyHelper HTTP API boundary."""

import os
import time
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.exceptions import APIError
from api.routers import auth, chat, homework, reports, therapists, wellness, mobile_v1, admin, post_consultation_onboarding
from database.postgres.connection import db_healthcheck


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")
        if request.url.path.startswith(("/v1/", "/me", "/admin", "/clients", "/therapists")):
            response.headers["Cache-Control"] = "no-store"
        return response


async def health(_request: Request):
    return JSONResponse({"status": "ok"})


async def health_db(_request: Request):
    latency = db_healthcheck()
    return JSONResponse({"status": "ok", "database": "postgresql", "latency_ms": latency})


async def api_error_handler(_request: Request, exc: APIError):
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}},
        status_code=exc.status_code,
    )


async def unhandled_error_handler(_request: Request, exc: Exception):
    return JSONResponse(
        {"error": {"code": "internal_server_error", "message": "Internal server error"}},
        status_code=500,
    )


app = FastAPI(debug=False,routes=[],exception_handlers={APIError: api_error_handler, Exception: unhandled_error_handler})
app.add_middleware(SecurityHeadersMiddleware)
app.add_route("/health", health, methods=["GET"])
app.add_route("/health/db", health_db, methods=["GET"])
app.include_router(auth.router)
app.include_router(wellness.router)
app.include_router(homework.router)
app.include_router(reports.router)
app.include_router(chat.router)
app.include_router(therapists.router)
app.include_router(mobile_v1.router)
app.include_router(admin.router)

app.include_router(post_consultation_onboarding.router)
