"""Single-user identity surface for the thesis proof of concept."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.models.database import get_db
from src.models.user import User
from src.schemas.auth import CurrentUserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme_preference: Literal["light", "dark"] | None = None


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    operation_id="getCurrentUser",
    summary="Get the local PoC user",
    responses={401: ERROR_RESPONSES[401]},
)
async def get_me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return _build_user_response(current_user)


@router.patch(
    "/me",
    response_model=CurrentUserResponse,
    operation_id="updateCurrentUser",
    summary="Update local PoC user preferences",
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
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        theme_preference=user.theme_preference or "dark",
    )
