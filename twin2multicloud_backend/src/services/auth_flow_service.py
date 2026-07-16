from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.jwt import create_access_token
from src.auth.providers.base import VerifiedExternalIdentity
from src.config import settings
from src.models.authentication import (
    AuthenticationEvent,
    AuthLoginTransaction,
    AuthSession,
    ExternalIdentity,
)
from src.models.user import User
from src.repositories.auth_repository import (
    AuthenticationEventRepository,
    AuthSessionRepository,
    AuthTransactionRepository,
    ExternalIdentityRepository,
)
from src.security.request_context import current_request_id
from src.utils.crypto import decrypt_scoped, encrypt_scoped


class AuthFlowError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        message: str,
        fix_suggestion: str,
        http_status: int,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.fix_suggestion = fix_suggestion
        self.http_status = http_status


@dataclass(frozen=True)
class StartedAuthTransaction:
    transaction: AuthLoginTransaction
    state: str
    poll_verifier: str
    pkce_verifier: str | None


@dataclass(frozen=True)
class IssuedAuthSession:
    access_token: str
    expires_in: int
    user: User


class AuthFlowService:
    SUPPORTED_PROVIDERS = {"google", "uibk"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.transactions = AuthTransactionRepository(db)
        self.identities = ExternalIdentityRepository(db)
        self.sessions = AuthSessionRepository(db)
        self.events = AuthenticationEventRepository(db)

    def start(self, provider: str) -> StartedAuthTransaction:
        self._require_provider(provider)
        now = _utc_now()
        self.transactions.delete_expired(now)
        state = secrets.token_urlsafe(32)
        poll_verifier = secrets.token_urlsafe(48)
        transaction = AuthLoginTransaction(
            id=str(uuid.uuid4()),
            provider=provider,
            purpose="login",
            state_digest=_digest(state),
            poll_verifier_digest=_digest(poll_verifier),
            status="pending",
            created_at=now,
            expires_at=now + timedelta(seconds=settings.AUTH_TRANSACTION_TTL_SECONDS),
        )
        pkce_verifier = secrets.token_urlsafe(64) if provider == "google" else None
        if pkce_verifier:
            transaction.pkce_verifier_encrypted = encrypt_scoped(
                pkce_verifier,
                "auth-system",
                transaction.id,
            )
        self.transactions.add(transaction)
        self._event("login_initiated", "accepted", provider, transaction.id, None, 201)
        self.db.flush()
        return StartedAuthTransaction(transaction, state, poll_verifier, pkce_verifier)

    def set_provider_request_id(self, transaction: AuthLoginTransaction, request_id: str) -> None:
        if not request_id:
            raise AuthFlowError(
                "PROVIDER_PROTOCOL_ERROR",
                "The identity provider login could not be started.",
                "Retry the sign-in operation.",
                502,
            )
        transaction.provider_request_id = request_id

    def claim_callback(self, provider: str, state: str) -> AuthLoginTransaction:
        self._require_provider(provider)
        if not state or len(state) > 256:
            raise self._invalid_callback()
        transaction = self.transactions.claim_callback(
            state_digest=_digest(state),
            provider=provider,
            now=_utc_now(),
        )
        if transaction is None:
            raise self._invalid_callback()
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def pkce_verifier(self, transaction: AuthLoginTransaction) -> str:
        encrypted = transaction.pkce_verifier_encrypted
        if not encrypted:
            raise AuthFlowError(
                "PROVIDER_PROTOCOL_ERROR",
                "The identity provider response could not be verified.",
                "Start a new sign-in operation.",
                400,
            )
        try:
            return decrypt_scoped(encrypted, "auth-system", transaction.id)
        except ValueError as exc:
            raise AuthFlowError(
                "AUTH_STATE_UNAVAILABLE",
                "The sign-in state could not be recovered.",
                "Start a new sign-in operation.",
                503,
            ) from exc

    def complete_callback(
        self,
        transaction: AuthLoginTransaction,
        identity_data: VerifiedExternalIdentity,
    ) -> User:
        try:
            user = self._resolve_identity(transaction.provider, identity_data)
            now = _utc_now()
            transaction.user_id = user.id
            transaction.status = "completed"
            transaction.completed_at = now
            transaction.pkce_verifier_encrypted = None
            self._event(
                "callback_verified",
                "succeeded",
                transaction.provider,
                transaction.id,
                user.id,
                200,
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError as exc:
            self.db.rollback()
            self.fail_callback(transaction.id, "IDENTITY_CONFLICT", 409)
            raise AuthFlowError(
                "IDENTITY_CONFLICT",
                "This provider identity is already linked.",
                "Use the account already linked to this identity or contact support.",
                409,
            ) from exc
        except AuthFlowError as exc:
            self.db.rollback()
            self.fail_callback(transaction.id, exc.error_code, exc.http_status)
            raise

    def fail_callback(self, transaction_id: str, error_code: str, http_status: int) -> None:
        transaction = self.transactions.get(transaction_id)
        if transaction is None:
            return
        transaction.status = "failed"
        transaction.error_code = error_code
        transaction.pkce_verifier_encrypted = None
        transaction.completed_at = _utc_now()
        self._event(
            "callback_verified",
            "rejected",
            transaction.provider,
            transaction.id,
            transaction.user_id,
            http_status,
        )
        self.db.commit()

    def exchange(self, transaction_id: str, poll_verifier: str) -> IssuedAuthSession | None:
        transaction = self._verified_transaction(transaction_id, poll_verifier)
        now = _utc_now()
        if _as_utc(transaction.expires_at) <= now:
            transaction.status = "expired"
            transaction.pkce_verifier_encrypted = None
            self.db.commit()
            raise AuthFlowError(
                "AUTH_TRANSACTION_EXPIRED",
                "The sign-in request expired.",
                "Start a new sign-in operation.",
                410,
            )
        if transaction.status == "pending":
            return None
        if transaction.status == "failed":
            raise self._failed_transaction_error(transaction.error_code)
        if transaction.status in {"cancelled", "expired"}:
            raise AuthFlowError(
                "AUTH_TRANSACTION_INACTIVE",
                "The sign-in request is no longer active.",
                "Start a new sign-in operation.",
                410,
            )
        if transaction.exchange_consumed_at is not None:
            raise AuthFlowError(
                "AUTH_TRANSACTION_REPLAYED",
                "The sign-in result was already consumed.",
                "Start a new sign-in operation.",
                409,
            )
        if transaction.user_id is None or not self.transactions.consume_exchange(
            transaction.id,
            now,
        ):
            raise AuthFlowError(
                "AUTH_TRANSACTION_REPLAYED",
                "The sign-in result was already consumed.",
                "Start a new sign-in operation.",
                409,
            )
        user = self.db.get(User, transaction.user_id)
        if user is None:
            raise AuthFlowError(
                "AUTH_ACCOUNT_UNAVAILABLE",
                "The authenticated account is unavailable.",
                "Contact support before retrying.",
                409,
            )
        expires_at = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        session = AuthSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            issued_at=now,
            expires_at=expires_at,
        )
        self.sessions.add(session)
        transaction.status = "consumed"
        transaction.pkce_verifier_encrypted = None
        self._event(
            "session_exchanged",
            "succeeded",
            transaction.provider,
            transaction.id,
            user.id,
            200,
        )
        self.db.commit()
        token = create_access_token(user.id, session.id, expires_at)
        return IssuedAuthSession(
            access_token=token,
            expires_in=max(1, int((expires_at - now).total_seconds())),
            user=user,
        )

    def cancel(self, transaction_id: str, poll_verifier: str) -> None:
        transaction = self._verified_transaction(transaction_id, poll_verifier)
        if not self.transactions.cancel(transaction.id, _utc_now()):
            raise AuthFlowError(
                "AUTH_TRANSACTION_INACTIVE",
                "The sign-in request is no longer active.",
                "No further action is required.",
                409,
            )
        transaction.pkce_verifier_encrypted = None
        self._event(
            "login_cancelled",
            "succeeded",
            transaction.provider,
            transaction.id,
            transaction.user_id,
            200,
        )
        self.db.commit()

    def revoke_session(self, session_id: str, user_id: str) -> None:
        self.sessions.revoke(session_id, user_id, _utc_now(), "user_logout")
        self._event("session_revoked", "succeeded", None, None, user_id, 200)
        self.db.commit()

    def _resolve_identity(
        self,
        provider: str,
        identity_data: VerifiedExternalIdentity,
    ) -> User:
        identity = self.identities.find(provider, identity_data.subject)
        now = _utc_now()
        if identity is not None:
            user = identity.user
            identity.email_at_login = identity_data.email
            identity.last_login_at = now
            user.name = identity_data.name or user.name
            user.picture_url = identity_data.picture_url or user.picture_url
            user.auth_provider = provider
            user.last_login_at = now
            return user

        existing_email = self.db.query(User).filter(
            func.lower(User.email) == identity_data.email.lower()
        ).first()
        if existing_email is not None:
            raise AuthFlowError(
                "IDENTITY_LINK_REQUIRED",
                "An account with this email address already exists.",
                "Sign in with the already linked provider. Explicit account linking is required.",
                409,
            )

        user = User(
            email=identity_data.email,
            name=identity_data.name,
            picture_url=identity_data.picture_url,
            auth_provider=provider,
            last_login_at=now,
        )
        self.db.add(user)
        self.db.flush()
        self.identities.add(
            ExternalIdentity(
                user_id=user.id,
                provider=provider,
                subject=identity_data.subject,
                email_at_login=identity_data.email,
                created_at=now,
                last_login_at=now,
            )
        )
        return user

    def _verified_transaction(
        self,
        transaction_id: str,
        poll_verifier: str,
    ) -> AuthLoginTransaction:
        transaction = self.transactions.get(transaction_id)
        supplied_digest = _digest(poll_verifier)
        stored_digest = transaction.poll_verifier_digest if transaction else "0" * 64
        if transaction is None or not secrets.compare_digest(supplied_digest, stored_digest):
            raise AuthFlowError(
                "AUTH_TRANSACTION_INVALID",
                "The sign-in request could not be verified.",
                "Start a new sign-in operation.",
                404,
            )
        return transaction

    def _event(
        self,
        action: str,
        outcome: str,
        provider: str | None,
        transaction_id: str | None,
        user_id: str | None,
        http_status: int,
    ) -> None:
        self.events.add(
            AuthenticationEvent(
                action=action,
                outcome=outcome,
                provider=provider,
                transaction_id=transaction_id,
                user_id=user_id,
                http_status=http_status,
                request_id=current_request_id(),
            )
        )

    @classmethod
    def _require_provider(cls, provider: str) -> None:
        if provider not in cls.SUPPORTED_PROVIDERS:
            raise AuthFlowError(
                "AUTH_PROVIDER_UNSUPPORTED",
                "The requested identity provider is not supported.",
                "Choose one of the providers reported by the capability endpoint.",
                404,
            )

    @staticmethod
    def _invalid_callback() -> AuthFlowError:
        return AuthFlowError(
            "AUTH_CALLBACK_INVALID",
            "The identity provider callback is invalid or expired.",
            "Start a new sign-in operation.",
            400,
        )

    @staticmethod
    def _failed_transaction_error(error_code: str | None) -> AuthFlowError:
        if error_code == "IDENTITY_LINK_REQUIRED":
            return AuthFlowError(
                error_code,
                "An account with this email address already exists.",
                "Sign in with the already linked provider. Explicit account linking is required.",
                409,
            )
        return AuthFlowError(
            error_code or "AUTH_PROVIDER_REJECTED",
            "The identity provider could not complete sign-in.",
            "Retry the sign-in operation or use another enabled provider.",
            401,
        )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
