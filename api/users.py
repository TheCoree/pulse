from fastapi import APIRouter, Depends, HTTPException, status

from schemas.user import UserPublic, ChangeUserRole, ChangePassword, ChangeUserPermissions

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

