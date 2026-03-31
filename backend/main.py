from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.debates import router as debates_router
from backend.routes.personas import router as personas_router
from backend.routes.sessions import router as sessions_router


app = FastAPI(title="Debate Arena API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(debates_router, prefix="/api")
app.include_router(personas_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
