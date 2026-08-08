from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from gamepulse.web_api.app import app as gamepulse_app


ASGIReceive = Callable[..., Awaitable[dict[str, Any]]]
ASGISend = Callable[..., Awaitable[None]]


class ApiPrefixAdapter:
    """Keep existing /api routes working when Services strips /api."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/api" or path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        prefixed_scope = dict(scope)
        suffix = path if path.startswith("/") else f"/{path}"
        prefixed_scope["path"] = f"/api{suffix}"

        raw_path = scope.get("raw_path")
        if isinstance(raw_path, bytes):
            raw_suffix = raw_path if raw_path.startswith(b"/") else b"/" + raw_path
            prefixed_scope["raw_path"] = b"/api" + raw_suffix

        await self.app(prefixed_scope, receive, send)


app = ApiPrefixAdapter(gamepulse_app)
