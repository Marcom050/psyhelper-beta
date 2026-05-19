"""FastAPI application exposing the minimal PsyHelper HTTP API boundary."""

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.exceptions import APIError
from api.routers import auth, chat, homework, reports, therapists, wellness


async def health(_request: Request):
    return JSONResponse({"status": "ok"})


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


app = FastAPI(
    debug=False,
    routes=[],
    exception_handlers={
        APIError: api_error_handler,
        Exception: unhandled_error_handler,
    },
)

app.add_route("/health", health, methods=["GET"])
app.include_router(auth.router)
app.include_router(wellness.router)
app.include_router(homework.router)
app.include_router(reports.router)
app.include_router(chat.router)
app.include_router(therapists.router)
