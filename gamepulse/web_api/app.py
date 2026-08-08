from fastapi import FastAPI

from gamepulse.web_api.routes.jobs import router as jobs_router

app = FastAPI(title="GamePulse API", version="1")
app.include_router(jobs_router)


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
