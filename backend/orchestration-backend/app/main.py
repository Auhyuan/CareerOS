import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.bootstrap
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.core.exceptions import register_exception_handlers
from app.common.core.lifespan import app_lifespan
from app.common.schemas.result import Result
from app.server.job.api import router as job_router
from app.server.mcp.config import get_mcp_config
from app.server.mcp.server import create_mcp_asgi_app
from app.server.spider.api import router as spider_router


def create_app() -> FastAPI:
    """Create the orchestration-backend FastAPI application."""
    app = FastAPI(lifespan=app_lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(job_router, prefix="/job", tags=["job orchestration"])
    app.include_router(spider_router, prefix="/spider", tags=["spider orchestration"])

    # MCP tools belong to orchestration because they are business capabilities.
    # If FastMCP is not installed yet, the main business APIs still start normally.
    mcp_config = get_mcp_config()
    mcp_app = create_mcp_asgi_app(mcp_config)
    if mcp_app is not None:
        # Store the MCP sub-application so the parent lifespan can start its
        # StreamableHTTP session manager before requests reach /mcp.
        app.state.mcp_app = mcp_app
        app.mount(mcp_config.mcp_mount_path, mcp_app)

    @app.get("/")
    def root_endpoint():
        """Return basic service health information."""
        return Result.success({"message": "orchestration-backend", "status": "ok"})

    return app


def print_routes(app: FastAPI) -> None:
    """Print registered routes for local startup checks."""
    print("Registered orchestration-backend routes:")
    for route in app.routes:
        print(route.path if hasattr(route, "path") else route)


def print_startup_banner() -> None:
    """Print a readable startup banner for orchestration-backend."""
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = os.getenv("FASTAPI_PORT", "8091")
    print(f"orchestration-backend starting: http://{host}:{port}")
    print("Public modules: /job, /spider, /mcp")


if __name__ == "__main__":
    app = create_app()
    print_startup_banner()
    print_routes(app)
    uvicorn.run("app.main:create_app", host=os.getenv("FASTAPI_HOST", "127.0.0.1"), port=int(os.getenv("FASTAPI_PORT", 8091)), loop="asyncio", workers=1, reload=True, factory=True)
