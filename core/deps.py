from fastapi import Depends, HTTPException, status, Path, Request
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_async_session
from core.config import settings
from models.user import User
from models.calendar_user import CalendarUser
from schemas.auth import GlobalRole


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> User:
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        username: str | None = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


class RoleChecker:
    def __init__(self, allowed_roles: list[GlobalRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас недостаточно прав (нужна роль: " + ", ".join(self.allowed_roles) + ")"
            )
        return user

# Сразу создадим готовые сокращения для удобства
allow_admin = RoleChecker([GlobalRole.ADMIN])
# allow_any_auth = get_current_user # это у тебя уже есть

async def require_editor(
    calendar_id: int = Path(...), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> CalendarUser:
    """
    Проверяет, есть ли у пользователя права на редактирование календаря.
    Если записи в CalendarUser нет — доступ запрещен.
    """
    query = select(CalendarUser).where(
        CalendarUser.calendar_id == calendar_id,
        CalendarUser.user_id == current_user.id
    )
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="У вас нет прав на редактирование этого календаря"
        )
    
    return link