from fastapi import APIRouter, Depends, status, HTTPException

from schemas.event import EventCreate, EventUpdate, EventsRangeQuery

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.event import Event
from models.user import User
from models.calendar_user import CalendarUser


from core.deps import require_editor, require_viewer, get_current_user
from core.database import get_async_session

import datetime

# --- API EVENTS ---

router = APIRouter(prefix='/calendars/{calendar_id}/events', tags=['Events'])


@router.get('/range')
async def get_events_range(
    calendar_id: int,
    query: EventsRangeQuery = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_viewer)
):
    # Логика пересечения:
    # 1. Событие началось ДО того, как закончился наш range (Event.start < query.to_date)
    # 2. Событие закончилось ПОСЛЕ того, как начался наш range (Event.end > query.from_date)
    stmt = (
        select(Event)
        .where(
            and_(
                Event.calendar_id == calendar_id,
                Event.start < query.to_date,
                Event.end > query.from_date
            )
        )
        .order_by(Event.start)
    )

    result = await db.execute(stmt)
    events = result.scalars().all()

    return events


@router.get('/{event_id}')
async def get_event(
    calendar_id: int,
    event_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_viewer)
):
    query = (
        select(Event)
        .options(joinedload(Event.calendar))
        .where(Event.id == event_id)
    )
    
    result = await db.execute(query)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Событие не найдено')

    return event
 

@router.post('/', status_code=status.HTTP_201_CREATED)
async def create_event(
    calendar_id: int,
    event_data: EventCreate,
    user: User = Depends(get_current_user),
    _ = Depends(require_editor), 
    db: AsyncSession = Depends(get_async_session)
):
    new_event = Event(
        title=event_data.title,
        description=event_data.description,
        start=event_data.start,
        end=event_data.end,
        calendar_id=calendar_id,
        created_by=user.id,
        created_at=datetime.datetime.now()
    )
    
    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)
    
    return new_event


@router.patch('/{event_id}')
async def update_event(
    calendar_id: int,
    event_id: int,
    data: EventUpdate,
    _ = Depends(require_editor),
    db: AsyncSession = Depends(get_async_session),
):
    stmt = select(Event).where(
        Event.id == event_id,
        Event.calendar_id == calendar_id
    )

    event = await db.scalar(stmt)

    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Событие не найдено')

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)

    return event


@router.delete('/{event_id}')
async def delete_event(
    calendar_id: int,
    event_id: int,
    _ = Depends(require_editor),
    db: AsyncSession = Depends(get_async_session)
):  
    stmt = select(Event).where(
        Event.id == event_id, 
        Event.calendar_id == calendar_id
    )
    event_to_delete = await db.scalar(stmt)
    
    if not event_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Событие не найдено')

    await db.delete(event_to_delete)
    await db.commit()


    return { 'detail': 'Событие успешно удалено' }


# --- STANDALONE EVENTS ---

standalone_router = APIRouter(prefix='/events', tags=['Standalone Events'])


@standalone_router.get('/{event_id}')
async def get_standalone_event(
    event_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Event).options(joinedload(Event.calendar)).where(Event.id == event_id)
    event = await db.scalar(stmt)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Событие не найдено')

    # Проверка прав (viewer или выше)
    perm_stmt = select(CalendarUser).where(
        CalendarUser.calendar_id == event.calendar_id,
        CalendarUser.user_id == current_user.id
    )
    perm = await db.scalar(perm_stmt)
    if not perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='У вас нет прав на просмотр этого события')

    return event


@standalone_router.get('/{event_id}/content')
async def get_standalone_event_content(
    event_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Получаем событие, чтобы узнать calendar_id
    stmt = select(Event).where(Event.id == event_id)
    event = await db.scalar(stmt)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Событие не найдено')

    # 2. Проверка прав
    perm_stmt = select(CalendarUser).where(
        CalendarUser.calendar_id == event.calendar_id,
        CalendarUser.user_id == current_user.id
    )
    perm = await db.scalar(perm_stmt)
    if not perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='У вас нет прав на просмотр этого события')

    # 3. Получаем контент
    from models.event_content import EventContent
    content_stmt = select(EventContent).where(EventContent.event_id == event_id).order_by(EventContent.order)
    result = await db.execute(content_stmt)
    return result.scalars().all()

