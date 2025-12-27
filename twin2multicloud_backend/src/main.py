from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.models.database import engine, Base
from src.api.routes import auth, twins, health
from src.api.routes.config import router as config_router, inline_router as config_inline_router
from src.api.routes.optimizer import router as optimizer_router
from src.api.routes.optimizer_config import router as optimizer_config_router

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Twin2MultiCloud Management API",
    version="1.0.0",
    description="Management API for Digital Twin multi-cloud deployments"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(twins.router)
app.include_router(health.router)
app.include_router(config_router)
app.include_router(config_inline_router)
app.include_router(optimizer_router)
app.include_router(optimizer_config_router)

@app.get("/")
async def root():
    return {"message": "Twin2MultiCloud Management API", "version": "1.0.0"}
