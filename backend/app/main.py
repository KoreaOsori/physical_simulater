from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import compare, connectome, fly, health, human, lab, simulation
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(connectome.router)
app.include_router(simulation.router)
app.include_router(fly.router)
app.include_router(human.router)
app.include_router(compare.router)
app.include_router(lab.router)
