from fastapi import APIRouter, Depends, HTTPException, status
import secrets
from datetime import datetime, timedelta, timezone
from schemas.user import UserPublic, ChangeUserRole, ChangePassword, ChangeUserPermissions, ProfileUpdate

from core.deps import get_current_user, allow_admin
from core.security import verify_password, get_password_hash
from core.database import get_async_session

from models.user import User

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# --- API USERS ---

router = APIRouter(prefix='/user', tags=['Users'])


@router.get('/me', response_model=UserPublic)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch('/me', response_model=UserPublic)
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    if data.username:
        # Check if username is already taken
        existing_user = await db.scalar(
            select(User).where(User.username == data.username, User.id != current_user.id)
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Пользователь с таким логином уже существует'
            )
        current_user.username = data.username
    
    if data.display_name is not None:
        current_user.display_name = data.display_name
        
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post('/telegram/generate-token')
async def generate_telegram_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    if current_user.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Telegram уже привязан к этому аккаунту'
        )

    token = secrets.token_urlsafe(16)
    current_user.telegram_connect_token = token
    current_user.telegram_connect_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    await db.commit()
    
    return {'token': token}


@router.delete('/telegram')
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Telegram не привязан'
        )
    
    current_user.telegram_id = None
    await db.commit()
    
    return {'detail': 'Telegram успешно отвязан'}


@router.get('/all-list')
async def get_all_users(
    admin: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(select(User))
    users = result.scalars().all()

    return users


@router.delete('/{user_id}')
async def delete_user(
    user_id: int,
    admin: User = Depends(allow_admin), 
    db: AsyncSession = Depends(get_async_session),
):
    user_to_delete = await db.scalar(
        select(User).where(User.id == user_id)
    )

    if not user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь не найден')
    
    if user_to_delete.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail='Вы не можете удалить свою собственную учетную запись'
        )
    
    await db.delete(user_to_delete)
    await db.commit()

    return { 'detail': f'Пользователь {user_to_delete.username} успешно удален' }
    

@router.patch('/change_password')
async def change_password(
    data: ChangePassword,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Текущий пароль не верный')
    
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Новый пароль не должен совпадать с текущим'
        )

    
    user.password_hash = get_password_hash(data.new_password)
    await db.commit()

    return { 'detail': 'Пароль успешно изменен' }


@router.patch('/{user_id}/role')
async def change_user_role(
    user_id: int,
    data: ChangeUserRole,
    admin: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_async_session),
):
    
    user_to_change_role = await db.scalar(
        select(User).where(User.id == user_id)
    )

    if not user_to_change_role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь не найден')
    
    if user_to_change_role.role == data.role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'This user is alredy {data.role}')
    
    username = user_to_change_role.username
    user_to_change_role.role = data.role
    await db.commit()

    return { 'detail': f'Роль {data.role} выбрана для {username}' }


@router.patch('/{user_id}/permissions')
async def change_user_permissions(
    user_id: int,
    data: ChangeUserPermissions,
    admin: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_async_session),
):
    user_to_change = await db.scalar(
        select(User).where(User.id == user_id)
    )

    if not user_to_change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь не найден')
    
    username = user_to_change.username
    user_to_change.is_items_corrector = data.is_items_corrector
    await db.commit()

    status_str = "назначен корректором" if data.is_items_corrector else "снят с должности корректора"
    return { 'detail': f'Пользователь {username} {status_str}' }
    

@router.get('/search', response_model=list[UserPublic])
async def search_users(
    q: str = "",
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    if not q:
        # Return some initial candidates (excluding current user)
        result = await db.execute(
            select(User)
            .where(User.id != current_user.id)
            .limit(5)
        )
        return result.scalars().all()
        
    if len(q) < 1:
        return []
        
    result = await db.execute(
        select(User)
        .where(
            (User.username.ilike(f"%{q}%")) | 
            (User.display_name.ilike(f"%{q}%"))
        )
        .where(User.id != current_user.id)
        .limit(10)
    )
    users = result.scalars().all()
    return users

