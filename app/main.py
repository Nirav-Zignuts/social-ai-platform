from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError,StarletteHTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.core.lifespan import lifespan
from app.api.v1.routes import auth_routes
from app.core.exception_handlers import (
    request_validation_exception_handler,
    pydantic_validation_exception_handler,
    http_exception_handler,
)

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

# Register global handlers for Pydantic / request validation errors (422)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)


@app.get("/health")
def health():
    return {"status": "healthy"}