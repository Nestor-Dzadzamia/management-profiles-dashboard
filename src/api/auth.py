from fastapi import APIRouter, HTTPException, status

from api.deps import AuthServiceDep, SessionDep
from config import get_settings
from schemas.auth import Token, UserCreate, UserLogin, UserRead
from services.auth import InvalidCredentialsError, LoginTakenError

router = APIRouter(tags=["auth"])


@router.post("/auth", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    service: AuthServiceDep,
    session: SessionDep,
) -> UserRead:
    try:
        user = await service.register(payload.login, payload.password)
    except LoginTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Login already taken") from None

    await session.commit()
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, service: AuthServiceDep) -> Token:
    try:
        token = await service.authenticate(payload.login, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from None

    return Token(access_token=token, expires_in=get_settings().jwt_ttl_seconds)
