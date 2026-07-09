from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError,StarletteHTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.core.lifespan import lifespan
from app.api.v1.routes import auth_routes, workspace_routes, generated_post_routes, notification_routes, instagram_routes
from app.core.exception_handlers import (
    request_validation_exception_handler,
    pydantic_validation_exception_handler,
    http_exception_handler,
    meta_integration_exception_handler,
)
from app.integrations.meta.exceptions import MetaIntegrationError

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Include API routes
app.include_router(
    auth_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    workspace_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    generated_post_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    notification_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    instagram_routes.router,
    prefix=settings.API_PREFIX,
)

# Register global handlers for Pydantic / request validation errors (422)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(MetaIntegrationError, meta_integration_exception_handler)


@app.get("/health")
def health():
    return {"status": "healthy"}