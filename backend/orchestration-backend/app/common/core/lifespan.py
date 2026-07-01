from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.common.db.postgres_db import check_postgres_health


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Manage orchestration-backend startup and shutdown lifecycle.

    The MCP ASGI app created by FastMCP owns a separate lifespan. FastAPI does
    not automatically run mounted sub-application lifespans, so the parent app
    must explicitly enter it. Without this step, /mcp requests can fail with
    500 because the StreamableHTTP session manager has not started.
    """
    check_postgres_health()
    print("PostgreSQL health check passed")

    async with AsyncExitStack() as stack:
        mcp_app: Any | None = getattr(app.state, "mcp_app", None)
        mcp_lifespan = getattr(mcp_app, "lifespan", None) if mcp_app is not None else None
        if mcp_lifespan is not None:
            # Start FastMCP's StreamableHTTP session manager together with FastAPI.
            await stack.enter_async_context(mcp_lifespan(mcp_app))
            print("MCP service lifecycle started")

        yield
