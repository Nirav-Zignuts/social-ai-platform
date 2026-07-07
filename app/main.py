from fastapi import FastAPI

from app.core.config import settings
from app.core.lifespan import lifespan

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "healthy"}