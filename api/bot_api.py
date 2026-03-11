from fastapi import APIRouter, Header, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_async_session
from core.config import settings
from models.user import User
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter(prefix='/bot', tags=['Bot API'])

class BotConnectRequest(BaseModel):
    token: str
    telegram_id: int

@router.post('/connect')
async def bot_connect(
    data: BotConnectRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_async_session)
):
    # Security check
    if authorization != settings.BOT_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot secret key"
        )

    # 1. Check if this telegram_id is already linked to someone else
    existing_user = await db.scalar(
        select(User).where(User.telegram_id == data.telegram_id)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот Telegram уже привязан к другому аккаунту"
        )

    # 2. Find user by token
    user = await db.scalar(
        select(User).where(User.telegram_connect_token == data.token)
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Неверный токен привязки"
        )

    # 3. Check token expiration
    if user.telegram_connect_token_expires_at:
        # Ensure we compare offset-aware datetimes
        expires_at = user.telegram_connect_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок действия токена истек"
            )

    # 4. Link account and cleanup
    user.telegram_id = data.telegram_id
    user.telegram_connect_token = None
    user.telegram_connect_token_expires_at = None

    username = user.username
    await db.commit()

    return {"ok": True, "username": username}
