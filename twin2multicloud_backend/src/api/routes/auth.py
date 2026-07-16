"""Provider-neutral production authentication API."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.auth.jwt import parse_bearer_token, verify_token
from src.auth.providers.google import GoogleOAuth, GoogleProviderError
from src.auth.providers.saml import UIBKSAMLProvider, is_saml_available
from src.config import settings
from src.models.database import get_db
from src.models.user import User
from src.schemas.auth import (
    AuthExchangeStatus,
    AuthProviderCapability,
    AuthProviderName,
    AuthProvidersResponse,
    AuthSessionCommand,
    AuthSessionExchangeResponse,
    AuthStartResponse,
    CurrentUserResponse,
)
from src.schemas.management_contracts import MessageResponse
from src.security.auth_rate_limit import AuthRateClass, enforce_auth_rate_limit
from src.security.request_context import current_request_id
from src.services.auth_flow_service import AuthFlowError, AuthFlowService


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme_preference: Literal["light", "dark"] | None = None


@router.get(
    "/providers",
    response_model=AuthProvidersResponse,
    operation_id="getAvailableAuthProviders",
    summary="Get authentication provider capabilities",
)
async def get_available_providers() -> AuthProvidersResponse:
    return AuthProvidersResponse(
        providers=[
            AuthProviderCapability(
                provider=AuthProviderName.UIBK,
                display_name="UIBK",
                enabled=settings.SAML_ENABLED and is_saml_available(),
                unavailable_reason=_uibk_unavailable_reason(),
            ),
            AuthProviderCapability(
                provider=AuthProviderName.GOOGLE,
                display_name="Google",
                enabled=settings.google_auth_enabled,
                unavailable_reason=None if settings.google_auth_enabled else "not_configured",
            ),
        ]
    )


@router.post(
    "/providers/{provider}/login",
    response_model=AuthStartResponse,
    status_code=201,
    operation_id="initiateExternalLogin",
    summary="Create a durable external login transaction",
    responses={400: ERROR_RESPONSES[400], 503: {"description": "Provider unavailable"}},
)
async def initiate_login(
    provider: AuthProviderName,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthStartResponse:
    await enforce_auth_rate_limit(request, response, AuthRateClass.LOGIN)
    _require_enabled(provider)
    service = AuthFlowService(db)
    started = service.start(provider.value)
    try:
        if provider is AuthProviderName.GOOGLE:
            authorization = GoogleOAuth().get_authorize_url(
                started.state,
                started.pkce_verifier or "",
            )
        else:
            saml_provider = UIBKSAMLProvider()
            authorization = saml_provider.get_login_url(
                saml_provider.request_data(),
                relay_state=started.state,
            )
            service.set_provider_request_id(
                started.transaction,
                authorization.request_id or "",
            )
        db.commit()
    except AuthFlowError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AuthFlowError(
            "AUTH_PROVIDER_UNAVAILABLE",
            "The identity provider login could not be started.",
            "Retry later or use another enabled provider.",
            503,
        ) from exc

    return AuthStartResponse(
        auth_url=authorization.auth_url,
        transaction_id=started.transaction.id,
        poll_verifier=started.poll_verifier,
        expires_at=started.transaction.expires_at,
        poll_interval_ms=settings.AUTH_POLL_INTERVAL_MS,
    )


@router.get(
    "/google/callback",
    response_class=HTMLResponse,
    include_in_schema=True,
    operation_id="handleGoogleCallback",
    summary="Verify the Google OAuth callback",
)
async def google_callback(
    state: str = Query(..., min_length=32, max_length=256),
    code: str | None = Query(default=None, min_length=1, max_length=4096),
    error: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    service = AuthFlowService(db)
    transaction_id: str | None = None
    try:
        transaction = service.claim_callback(AuthProviderName.GOOGLE.value, state)
        transaction_id = transaction.id
        if error is not None or code is None:
            service.fail_callback(transaction.id, "AUTH_PROVIDER_REJECTED", 401)
            return _callback_page(False, 401)
        try:
            identity = await GoogleOAuth().handle_callback(
                code,
                service.pkce_verifier(transaction),
            )
        except GoogleProviderError:
            service.fail_callback(transaction.id, "AUTH_PROVIDER_REJECTED", 401)
            return _callback_page(False, 401)
        service.complete_callback(transaction, identity)
        return _callback_page(True, 200)
    except AuthFlowError as exc:
        return _callback_page(False, exc.http_status)
    except Exception:
        _best_effort_fail(service, transaction_id)
        return _callback_page(False, 503)


@router.post(
    "/uibk/callback",
    response_class=HTMLResponse,
    include_in_schema=True,
    operation_id="handleUibkCallback",
    summary="Verify the UIBK SAML callback",
)
async def uibk_callback(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not settings.SAML_ENABLED or not is_saml_available():
        return _callback_page(False, 503)
    form = await request.form()
    relay_state = form.get("RelayState")
    if not isinstance(relay_state, str):
        return _callback_page(False, 400)
    service = AuthFlowService(db)
    transaction_id: str | None = None
    try:
        transaction = service.claim_callback(AuthProviderName.UIBK.value, relay_state)
        transaction_id = transaction.id
        if not transaction.provider_request_id:
            service.fail_callback(transaction.id, "PROVIDER_PROTOCOL_ERROR", 400)
            return _callback_page(False, 400)
        post_data = {
            key: value
            for key, value in form.multi_items()
            if isinstance(key, str) and isinstance(value, str)
        }
        provider = UIBKSAMLProvider()
        try:
            identity = await provider.handle_callback(
                provider.request_data(
                    query=dict(request.query_params),
                    post=post_data,
                ),
                post_data,
                transaction.provider_request_id,
            )
        except Exception:
            service.fail_callback(transaction.id, "AUTH_PROVIDER_REJECTED", 401)
            return _callback_page(False, 401)
        service.complete_callback(transaction, identity)
        return _callback_page(True, 200)
    except AuthFlowError as exc:
        return _callback_page(False, exc.http_status)
    except Exception:
        _best_effort_fail(service, transaction_id)
        return _callback_page(False, 503)


@router.post(
    "/session/exchange",
    response_model=AuthSessionExchangeResponse,
    operation_id="exchangeAuthenticationSession",
    summary="Poll and consume an external login result",
    responses={409: ERROR_RESPONSES[409]},
)
async def exchange_session(
    command: AuthSessionCommand,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionExchangeResponse:
    await enforce_auth_rate_limit(request, response, AuthRateClass.EXCHANGE)
    issued = AuthFlowService(db).exchange(command.transaction_id, command.poll_verifier)
    if issued is None:
        response.status_code = 202
        return AuthSessionExchangeResponse(status=AuthExchangeStatus.PENDING)
    return AuthSessionExchangeResponse(
        status=AuthExchangeStatus.AUTHENTICATED,
        access_token=issued.access_token,
        token_type="bearer",  # nosec B106
        expires_in=issued.expires_in,
        user=_build_user_response(issued.user),
    )


@router.post(
    "/session/cancel",
    response_model=MessageResponse,
    operation_id="cancelAuthenticationSession",
    summary="Cancel an unconsumed external login transaction",
)
async def cancel_session(
    command: AuthSessionCommand,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MessageResponse:
    await enforce_auth_rate_limit(request, response, AuthRateClass.EXCHANGE)
    AuthFlowService(db).cancel(command.transaction_id, command.poll_verifier)
    return MessageResponse(message="Sign-in cancelled")


@router.post(
    "/logout",
    response_model=MessageResponse,
    operation_id="logoutCurrentSession",
    summary="Revoke the current server-side authentication session",
)
async def logout(
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    token = parse_bearer_token(authorization)
    claims = verify_token(token) if token else None
    if claims is not None and claims.user_id == current_user.id:
        AuthFlowService(db).revoke_session(claims.session_id, current_user.id)
    return MessageResponse(message="Signed out")


@router.get(
    "/uibk/metadata",
    operation_id="getUibkSpMetadata",
    summary="Serve UIBK service-provider metadata",
)
async def uibk_metadata() -> Response:
    if not settings.SAML_ENABLED or not is_saml_available():
        raise AuthFlowError(
            "AUTH_PROVIDER_UNAVAILABLE",
            "UIBK authentication is not enabled.",
            "Enable and fully configure SAML before requesting metadata.",
            503,
        )
    return Response(
        content=UIBKSAMLProvider().get_metadata(),
        media_type="application/xml",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    operation_id="getCurrentUser",
    summary="Get the current authenticated user",
    responses={401: ERROR_RESPONSES[401]},
)
async def get_me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return _build_user_response(current_user)


@router.patch(
    "/me",
    response_model=CurrentUserResponse,
    operation_id="updateCurrentUser",
    summary="Update current user preferences",
    responses={401: ERROR_RESPONSES[401], 422: ERROR_RESPONSES[422]},
)
async def update_me(
    updates: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    if updates.theme_preference is not None:
        current_user.theme_preference = updates.theme_preference
    db.commit()
    db.refresh(current_user)
    return _build_user_response(current_user)


def _build_user_response(user: User) -> CurrentUserResponse:
    linked = {identity.provider for identity in user.external_identities}
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        picture_url=user.picture_url,
        auth_provider=user.auth_provider,
        theme_preference=user.theme_preference or "dark",
        uibk_linked=AuthProviderName.UIBK.value in linked,
        google_linked=AuthProviderName.GOOGLE.value in linked,
    )


def _require_enabled(provider: AuthProviderName) -> None:
    enabled = (
        settings.google_auth_enabled
        if provider is AuthProviderName.GOOGLE
        else settings.SAML_ENABLED and is_saml_available()
    )
    if not enabled:
        raise AuthFlowError(
            "AUTH_PROVIDER_UNAVAILABLE",
            "The requested identity provider is not enabled.",
            "Choose an enabled provider reported by the capability endpoint.",
            503,
        )


def _uibk_unavailable_reason() -> str | None:
    if not settings.SAML_ENABLED:
        return "not_enabled"
    if not is_saml_available():
        return "dependency_unavailable"
    return None


def _callback_page(success: bool, status_code: int) -> HTMLResponse:
    title = "Sign-in complete" if success else "Sign-in failed"
    message = (
        "You can return to Twin2MultiCloud."
        if success
        else "Return to Twin2MultiCloud and start a new sign-in operation."
    )
    body = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body><main><h1>{title}</h1>"
        f"<p>{message}</p></main></body></html>"
    )
    return HTMLResponse(
        body,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _best_effort_fail(service: AuthFlowService, transaction_id: str | None) -> None:
    if transaction_id is None:
        return
    try:
        service.db.rollback()
        service.fail_callback(transaction_id, "AUTH_SERVICE_UNAVAILABLE", 503)
    except Exception:
        service.db.rollback()
        logger.error(
            "Authentication callback failure could not be persisted",
            extra={
                "request_id": current_request_id(),
                "transaction_id": transaction_id,
            },
        )
