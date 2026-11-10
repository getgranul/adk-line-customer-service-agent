"""Construct the HTTP application and register its routes."""

from fastapi import FastAPI

from line_customer_service.api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Create an application instance without connecting to external services."""
    app = FastAPI(title="LINE Customer Service Agent")
    app.include_router(health_router)
    return app
