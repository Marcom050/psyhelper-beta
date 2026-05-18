"""Minimal FastAPI-compatible surface used when the external package is unavailable.

This project pins Starlette in its current environment. The API code relies only
on the small FastAPI surface below: ``FastAPI`` application construction and
``APIRouter`` route registration. The public HTTP behavior remains ASGI/Starlette
compatible and can be swapped to the upstream FastAPI package by installing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class FastAPI(Starlette):
    """Small compatibility subclass matching the app constructor used here."""

    def include_router(self, router: "APIRouter") -> None:
        self.router.routes.extend(router.routes)


@dataclass
class APIRouter:
    """Collect route declarations before inclusion in the application."""

    routes: list[Route] = field(default_factory=list)

    def add_api_route(self, path: str, endpoint: Callable, *, methods: list[str] | None = None) -> None:
        self.routes.append(Route(path, endpoint, methods=methods))

    def get(self, path: str):
        def decorator(endpoint: Callable):
            self.add_api_route(path, endpoint, methods=["GET"])
            return endpoint

        return decorator

    def post(self, path: str):
        def decorator(endpoint: Callable):
            self.add_api_route(path, endpoint, methods=["POST"])
            return endpoint

        return decorator


__all__ = ["APIRouter", "FastAPI", "HTTPException", "JSONResponse", "Request"]
