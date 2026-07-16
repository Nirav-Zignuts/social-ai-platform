from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, StarletteHTTPException
from pydantic import ValidationError
import os

from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.api.v1.routes import (
    auth_routes,
    workspace_routes,
    generated_post_routes,
    notification_routes,
    instagram_routes,
    google_oauth_routes,
    internal_cron_routes,
    onboarding_chat_routes,
    analytics_routes,
)
from app.core.exception_handlers import (
    request_validation_exception_handler,
    pydantic_validation_exception_handler,
    http_exception_handler,
    meta_integration_exception_handler,
    google_integration_exception_handler,
)
from app.integrations.google.exceptions import GoogleIntegrationError
from app.integrations.meta.exceptions import MetaIntegrationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

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
app.include_router(
    google_oauth_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    internal_cron_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    onboarding_chat_routes.router,
    prefix=settings.API_PREFIX,
)
app.include_router(
    analytics_routes.router,
    prefix=settings.API_PREFIX,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in [
            settings.FRONTEND_URL,
            *os.getenv("CORS_ORIGINS", "").split(","),
        ]
        if origin.strip()
    ]
    or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global handlers for Pydantic / request validation errors (422)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(MetaIntegrationError, meta_integration_exception_handler)
app.add_exception_handler(GoogleIntegrationError, google_integration_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.get("/health")
@limiter.exempt
def health():
    return {"status": "healthy"}
