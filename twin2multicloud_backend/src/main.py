from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.config import settings
from src.models.database import engine
from src.database_startup import initialize_database_schema
from src.api.routes import (
    auth,
    cloud_access,
    cloud_bootstrap,
    cloud_connections,
    credential_security_events,
    health,
    twin_operations,
    twins,
)
from src.api.routes.config import router as config_router, inline_router as config_inline_router
from src.api.routes.optimizer import router as optimizer_router
from src.api.routes.optimizer_config import router as optimizer_config_router
from src.api.routes.optimizer_runs import router as optimizer_runs_router
from src.api.routes.pricing_refresh import router as pricing_refresh_router
from src.api.routes.pricing_review import router as pricing_review_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.deployer import router as deployer_router
from src.api.routes.sse import router as sse_router
from src.services.deployment_stream_service import start_reaper
from src.security.rate_limit import (
    CredentialRateLimitExceeded,
    CredentialSecurityControlUnavailable,
)
from src.security.request_context import RequestContextMiddleware, current_request_id
from src.security.transport import ProductionTransportMiddleware
from src.services.credential_security_audit_service import CredentialAuditWriteFailed
from src.security.auth_rate_limit import (
    AuthRateLimitExceeded,
    AuthSecurityControlUnavailable,
)
from src.services.auth_flow_service import AuthFlowError

initialize_database_schema(engine, settings.DATABASE_URL)

if settings.SAML_ENABLED and not auth.is_saml_available():
    raise RuntimeError("SAML_ENABLED requires the python3-saml runtime dependency")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks and optional seed data during app startup."""
    start_reaper()
    if settings.SEED_DATA:
        from scripts.seed_twins import seed_if_needed
        await seed_if_needed()
    yield


app = FastAPI(
    title="Twin2MultiCloud Management API",
    version="1.0.0",
    description="Management API for Digital Twin multi-cloud deployments",
    lifespan=lifespan,
)

app.add_middleware(
    ProductionTransportMiddleware,
    require_https=bool(settings.REQUIRE_HTTPS),
    trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(CredentialRateLimitExceeded)
async def credential_rate_limit_handler(
    _request: Request,
    exc: CredentialRateLimitExceeded,
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers=exc.headers,
        content={
            "error_code": "RATE_LIMITED",
            "message": "Too many credential operations were requested.",
            "fix_suggestion": "Wait for the Retry-After interval before retrying.",
            "http_status": 429,
            "request_id": current_request_id(),
        },
    )


@app.exception_handler(CredentialSecurityControlUnavailable)
@app.exception_handler(CredentialAuditWriteFailed)
async def credential_security_unavailable_handler(
    _request: Request,
    _exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error_code": "SECURITY_CONTROL_UNAVAILABLE",
            "message": "A required credential security control is unavailable.",
            "fix_suggestion": "Retry after the service operator restores the security control.",
            "http_status": 503,
            "request_id": current_request_id(),
        },
    )


@app.exception_handler(AuthFlowError)
async def auth_flow_error_handler(_request: Request, exc: AuthFlowError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "fix_suggestion": exc.fix_suggestion,
            "http_status": exc.http_status,
            "request_id": current_request_id(),
        },
    )


@app.exception_handler(AuthRateLimitExceeded)
async def auth_rate_limit_handler(
    _request: Request,
    exc: AuthRateLimitExceeded,
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers=exc.headers,
        content={
            "error_code": "RATE_LIMITED",
            "message": "Too many authentication requests were submitted.",
            "fix_suggestion": "Wait for the Retry-After interval before retrying.",
            "http_status": 429,
            "request_id": current_request_id(),
        },
    )


@app.exception_handler(AuthSecurityControlUnavailable)
async def auth_security_unavailable_handler(
    _request: Request,
    _exc: AuthSecurityControlUnavailable,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error_code": "SECURITY_CONTROL_UNAVAILABLE",
            "message": "A required authentication security control is unavailable.",
            "fix_suggestion": "Retry after the service operator restores the security control.",
            "http_status": 503,
            "request_id": current_request_id(),
        },
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
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routes
app.include_router(auth.router)
app.include_router(twins.router)
app.include_router(twin_operations.router)
app.include_router(health.router)
app.include_router(cloud_connections.router)
app.include_router(credential_security_events.router)
app.include_router(cloud_bootstrap.router)
app.include_router(cloud_access.router)
app.include_router(config_router)
app.include_router(config_inline_router)
app.include_router(optimizer_router)
app.include_router(optimizer_config_router)
app.include_router(optimizer_runs_router)
app.include_router(pricing_refresh_router)
app.include_router(pricing_review_router)
app.include_router(dashboard_router)
app.include_router(deployer_router)
app.include_router(sse_router)
if settings.ENABLE_TEST_ENDPOINTS:
    from src.api.routes.test_endpoints import router as test_endpoints_router
    app.include_router(test_endpoints_router)

@app.get("/")
async def root():
    return {"message": "Twin2MultiCloud Management API", "version": "1.0.0"}
