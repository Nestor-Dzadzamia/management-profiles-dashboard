from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.deps import AuthServiceDep, SessionDep
from config import get_settings
from services.user import InvalidCredentialsError, LoginTakenError


class RegisterRequest(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    repeat_password: str

    @model_validator(mode="after")
    def password_match(self) -> "RegisterRequest":
        if self.password != self.repeat_password:
            raise ValueError("Passwords don't match")
        return self


class LoginRequest(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


router = APIRouter(tags=["auth"])


@router.post("/auth", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    service: AuthServiceDep,
    session: SessionDep,
) -> UserResponse:
    try:
        user = await service.register(payload.login, payload.password)
    except LoginTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Login already taken") from None

    await session.commit()
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    try:
        token = await service.authenticate(payload.login, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from None

    return TokenResponse(access_token=token, expires_in=get_settings().jwt_ttl_seconds)
