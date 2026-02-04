from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Response
from fastapi.security import OAuth2PasswordRequestForm

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_async_session
from core.security import verify_password, create_access_token, get_password_hash, create_refresh_token

from models.user import User

from schemas.auth import *

# --- API AUTH ---

router = APIRouter(prefix='/auth', tags=['Authentication'])


@router.post('/register', status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(User).where(User.username == user_data.username))

    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail='Пользователь с таким логином уже существует'
        )

    new_user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=GlobalRole.USER
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return { 'detail': 'Пользователь успешно создан', 'username': new_user.username }


@router.post('/login')
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Неверное имя пользователя или пароль',
        )

    access_token = create_access_token(
        data={'sub': user.username},
        expires_delta=timedelta(minutes=60),
    )

    refresh_token = create_refresh_token(
        data={'sub': user.username}
    )

    user.refresh_token = refresh_token
    await db.commit()

    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        samesite='lax',
        path='/',
    )

    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        samesite='lax',
        path='/',
    )

    return {'ok': True}


@router.post("/refresh")
async def refresh_session(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_async_session),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    result = await db.execute(
        select(User).where(User.refresh_token == refresh_token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    new_access = create_access_token(data={"sub": user.username})
    new_refresh = create_refresh_token(data={"sub": user.username})

    user.refresh_token = new_refresh
    await db.commit()

    # 🔥 СТАВИМ COOKIE
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        samesite="lax",
        path="/",
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        samesite="lax",
        path="/",  # ❗ КРИТИЧНО для middleware
    )

    return {"ok": True}