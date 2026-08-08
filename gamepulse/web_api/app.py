from fastapi import FastAPI

app = FastAPI(title="GamePulse API", version="1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
