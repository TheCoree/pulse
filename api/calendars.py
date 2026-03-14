from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload

from core.database import get_async_session
from core.deps import get_current_user

from schemas.auth import LocalRole
from models.user import User
from models.calendar import Calendar
from models.calendar_user import CalendarUser
from models.event import Event
from models.event_content import EventContent
from schemas.calendar import CalendarCreate, CalendarUpdate, CalendarPublic, AddUserToCalendar, ParticipantPublic
from schemas.auth import LocalRole

# --- API CALENDARS ---

router = APIRouter(prefix='/calendars', tags=['Calendars'])


@router.get('/my', response_model=list[CalendarPublic])
async def get_my_calendars(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Get all calendars user is part of
    query = (
        select(Calendar)
        .join(CalendarUser)
        .where(CalendarUser.user_id == current_user.id)
        .options(selectinload(Calendar.user_links).joinedload(CalendarUser.user))
    )
    
    result = await db.execute(query)
    calendars = result.scalars().all()
    
    response = []
    for cal in calendars:
        cal_data = CalendarPublic.model_validate(cal)
        # Find current user's role
        my_link_role = next((link.role for link in cal.user_links if link.user_id == current_user.id), LocalRole.VIEWER)
        cal_data.role = LocalRole(my_link_role)
        
        # Build participants list
        cal_data.participants = [
            ParticipantPublic(
                id=link.user.id,
                username=link.user.username,
                display_name=link.user.display_name,
                role=LocalRole(link.role)
            ) for link in cal.user_links
        ]
        response.append(cal_data)
        
    return response


@router.post('/', status_code=status.HTTP_201_CREATED, response_model=CalendarPublic)
async def create_calendar(
    data: CalendarCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if await db.scalar(select(Calendar).where(Calendar.name == data.name)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Календарь с таким названием уже есть')

    new_calendar = Calendar(
        name=data.name, 
        description=data.description,
        type=data.type
    )
    db.add(new_calendar)
    await db.flush() 

    calendar_link = CalendarUser(
        user_id=current_user.id,
        calendar_id=new_calendar.id,
        role=LocalRole.OWNER
    )
    db.add(calendar_link)
    
    await db.commit()
    await db.refresh(new_calendar)
    
    # Reload for participants
    result = await db.execute(
        select(Calendar)
        .where(Calendar.id == new_calendar.id)
        .options(selectinload(Calendar.user_links).joinedload(CalendarUser.user))
    )
    new_calendar = result.scalar_one()
    
    cal_data = CalendarPublic.model_validate(new_calendar)
    cal_data.role = LocalRole.OWNER
    cal_data.participants = [
        ParticipantPublic(
            id=current_user.id,
            username=current_user.username,
            display_name=current_user.display_name,
            role=LocalRole.OWNER
        )
    ]
    return cal_data


@router.patch('/{calendar_id}', response_model=CalendarPublic)
async def update_calendar(
    calendar_id: int,
    data: CalendarUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Check if user is owner
    role_link = await db.scalar(
        select(CalendarUser).where(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.user_id == current_user.id
        )
    )
    
    if not role_link or role_link.role != LocalRole.OWNER:
        raise HTTPException(status_code=403, detail="Только владелец может изменять настройки календаря")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    await db.execute(
        update(Calendar)
        .where(Calendar.id == calendar_id)
        .values(**update_data)
    )
    await db.commit()
    
    # Return updated calendar
    result = await db.execute(
        select(Calendar)
        .where(Calendar.id == calendar_id)
        .options(selectinload(Calendar.user_links).joinedload(CalendarUser.user))
    )
    cal = result.scalar_one()
    
    cal_data = CalendarPublic.model_validate(cal)
    cal_data.role = LocalRole.OWNER
    cal_data.participants = [
        ParticipantPublic(
            id=link.user.id,
            username=link.user.username,
            display_name=link.user.display_name,
            role=LocalRole(link.role)
        ) for link in cal.user_links
    ]
    return cal_data


@router.delete('/{calendar_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar(
    calendar_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    role_link = await db.scalar(
        select(CalendarUser).where(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.user_id == current_user.id
        )
    )
    
    if not role_link or role_link.role != LocalRole.OWNER:
        raise HTTPException(status_code=403, detail="Только владелец может удалить календарь")

    # Manually delete related records because DB schema might not have ON DELETE CASCADE
    # 1. Delete EventContents for all events in this calendar
    events_subquery = select(Event.id).where(Event.calendar_id == calendar_id)
    await db.execute(delete(EventContent).where(EventContent.event_id.in_(events_subquery)))
    
    # 2. Delete Events
    await db.execute(delete(Event).where(Event.calendar_id == calendar_id))
    
    # 3. Delete CalendarUser links
    await db.execute(delete(CalendarUser).where(CalendarUser.calendar_id == calendar_id))

    # 4. Finally delete the Calendar itself
    await db.execute(delete(Calendar).where(Calendar.id == calendar_id))
    
    await db.commit()
    return None


@router.post('/{calendar_id}/users', status_code=status.HTTP_200_OK)
async def add_user_to_calendar(
    calendar_id: int,
    data: AddUserToCalendar,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Check if current_user is owner
    role_link = await db.scalar(
        select(CalendarUser).where(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.user_id == current_user.id
        )
    )
    
    if not role_link or role_link.role != LocalRole.OWNER:
        raise HTTPException(status_code=403, detail="Только владелец может управлять доступом")

    # If role is OWNER, downgrade current owner to editor
    if data.role == LocalRole.OWNER:
        # role_link is our link (current owner)
        role_link.role = LocalRole.EDITOR

    # Get target user
    target_user = await db.scalar(select(User).where(User.username == data.username))
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Check if target user already in calendar
    existing_link = await db.scalar(
        select(CalendarUser).where(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.user_id == target_user.id
        )
    )

    if existing_link:
        existing_link.role = data.role
    else:
        new_link = CalendarUser(
            user_id=target_user.id,
            calendar_id=calendar_id,
            role=data.role
        )
        db.add(new_link)

    await db.commit()
    return {"status": "ok"}


@router.delete('/{calendar_id}/users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_calendar(
    calendar_id: int,
    user_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Determine target user ID
    if user_id == "me":
        target_user_id = current_user.id
    else:
        try:
            target_user_id = int(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный ID пользователя")

    # Owner can remove anyone, others can only remove themselves
    role_link = await db.scalar(
        select(CalendarUser).where(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.user_id == current_user.id
        )
    )
    
    if not role_link:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    if role_link.role != LocalRole.OWNER and current_user.id != target_user_id:
        raise HTTPException(status_code=403, detail="Только владелец может удалять других участников")

    await db.execute(
        delete(CalendarUser)
        .where(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.user_id == target_user_id
        )
    )
    await db.commit()
    return None
