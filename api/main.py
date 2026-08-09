from fastapi import FastAPI

app = FastAPI(
    title="RML API",
    description="API for RML statistics and player data",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "RML API is running"
    }