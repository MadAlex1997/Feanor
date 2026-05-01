from fastapi import FastAPI

from .middleware import RequestIDMiddleware
from .routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fëanor API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestIDMiddleware)

    app.include_router(health.router)

    return app


app = create_app()
