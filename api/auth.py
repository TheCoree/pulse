from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Cookie,
    Response,
    Request,
)
from fastapi.security import OAuth2PasswordRequestForm

from datetime import timedelta, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete

from core.deps import get_current_user
from core.database import get_async_session
from core.security import (
    verify_password,
    create_access_token,
    get_password_hash,
    create_refresh_token,
)

from models.user import User
from models.refresh_session import RefreshSession

from schemas.auth import *

# --- API AUTH ---

router = APIRouter(prefix='/auth', tags=['Authentication'])


# ======================================================
# REGISTER
# ======================================================

@router.post('/register', status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )

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

    return {
        'detail': 'Пользователь успешно создан',
        'username': new_user.username,
    }


# ======================================================
# LOGIN
# ======================================================

@router.post('/login')
async def login(
    request: Request,
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

    # --- CREATE REFRESH SESSION ---
    session = RefreshSession(
        user_id=user.id,
        refresh_token=refresh_token,
        user_agent=request.headers.get('user-agent'),
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )

    db.add(session)
    await db.commit()

    # --- COOKIES ---
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


# ======================================================
# REFRESH
# ======================================================

@router.post('/refresh')
async def refresh_session(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_async_session),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing refresh token',
        )

    result = await db.execute(
        select(RefreshSession)
        .options(selectinload(RefreshSession.user))  # 🔥 ВАЖНО
        .where(RefreshSession.refresh_token == refresh_token)
    )
    session = result.scalar_one_or_none()

    # Обработка возможного отсутствия часового пояса уexpires_at из БД
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not session or expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid refresh token',
        )

    user = session.user

    new_access = create_access_token(
        data={'sub': user.username}
    )

    new_refresh = create_refresh_token(
        data={'sub': user.username}
    )

    session.refresh_token = new_refresh
    session.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    await db.commit()

    response.set_cookie(
        key='access_token',
        value=new_access,
        httponly=True,
        samesite='lax',
        path='/',
    )

    response.set_cookie(
        key='refresh_token',
        value=new_refresh,
        httponly=True,
        samesite='lax',
        path='/',
    )

    return {'ok': True}


# ======================================================
# LOGOUT (CURRENT DEVICE)
# ======================================================

@router.post('/logout')
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_async_session),
):
    if refresh_token:
        await db.execute(
            delete(RefreshSession)
            .where(RefreshSession.refresh_token == refresh_token)
        )
        await db.commit()

    response.delete_cookie('access_token', httponly=True, samesite='lax')
    response.delete_cookie('refresh_token', httponly=True, samesite='lax')

    return {'ok': True}


# ======================================================
# LOGOUT ALL DEVICES
# ======================================================

@router.post('/logout/all')
async def logout_all(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await db.execute(
        delete(RefreshSession)
        .where(RefreshSession.user_id == user.id)
    )
    await db.commit()

    return {'ok': True}
