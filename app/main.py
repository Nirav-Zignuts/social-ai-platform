from fastapi import FastAPI

app = FastAPI(
    title="AI Marketing Platform",
    version="1.0.0",
)


@app.get("/")
def root():
    return {"message": "AI Marketing Platform API"}


@app.get("/health")
def health():
    return {"status": "healthy"}