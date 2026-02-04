from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_async_session
from core.deps import get_current_user

from models.user import User
from models.calendar import Calendar
from models.calendar_user import CalendarUser

# --- API CALENDARS ---

router = APIRouter(prefix='/calendars', tags=['Calendars'])


@router.get('/all')
async def get_all_calendars(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(
        select(Calendar)
    )
    calendars = result.scalars().all()

    return calendars


@router.post('/', status_code=status.HTTP_201_CREATED)
async def create_calendar(
    name: str,
    description: str | None = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    if await db.scalar(select(Calendar).where(Calendar.name == name)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Календарь с таким назвнием уже есть')

    new_calendar = Calendar(name=name, description=description)
    db.add(new_calendar)
    
    await db.flush() 

    calendar_link = CalendarUser(
        user_id=current_user.id,
        calendar_id=new_calendar.id,
        role='editor'
    )
    db.add(calendar_link)
    
    await db.commit()
    await db.refresh(new_calendar)
    
    return new_calendar


@router.get('/my')
async def get_my_calendars(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    query = (
        select(Calendar)
        .join(CalendarUser)
        .where(CalendarUser.user_id == current_user.id)
    )
    
    result = await db.execute(query)
    calendars = result.scalars().all()
    
    return calendars
