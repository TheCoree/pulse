from fastapi import APIRouter, Depends, status, HTTPException

from schemas.event import EventCreate, EventUpdate, EventsRangeQuery

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.event import Event
from models.user import User

from core.deps import require_editor, get_current_user
from core.database import get_async_session

import datetime

# --- API EVENTS ---

router = APIRouter(prefix='/calendars/{calendar_id}/events', tags=['Events'])


@router.get('/range')
async def get_events_range(
    calendar_id: int,
    query: EventsRangeQuery = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user) 
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
    event_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
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
