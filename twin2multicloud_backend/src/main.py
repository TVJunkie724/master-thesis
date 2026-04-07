from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.models.database import engine, Base
from src.api.routes import auth, twins, health
from src.api.routes.config import router as config_router, inline_router as config_inline_router
from src.api.routes.optimizer import router as optimizer_router
from src.api.routes.optimizer_config import router as optimizer_config_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.deployer import router as deployer_router
from src.api.routes.sse import router as sse_router, start_reaper
from src.api.routes.test_endpoints import router as test_endpoints_router

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Twin2MultiCloud Management API",
    version="1.0.0",
    description="Management API for Digital Twin multi-cloud deployments"
)

# CORS
# In DEBUG mode Flutter Web picks a random localhost port per session, so
# we accept any localhost/127.0.0.1 origin via a regex. In production we
# stay strict with the explicit CORS_ORIGINS whitelist from settings.
if settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
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
app.include_router(dashboard_router)
app.include_router(deployer_router)
app.include_router(sse_router)
app.include_router(test_endpoints_router)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup."""
    start_reaper()
    # Seed test data if enabled in settings
    if settings.SEED_DATA:
        from scripts.seed_twins import seed_if_needed
        await seed_if_needed()

@app.get("/")
async def root():
    return {"message": "Twin2MultiCloud Management API", "version": "1.0.0"}

