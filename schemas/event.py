from pydantic import BaseModel, Field
from datetime import datetime

class EventsRangeQuery(BaseModel):
    from_date: datetime
    to_date: datetime


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=4096)
    
    start: datetime
    end: datetime


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start: datetime | None = None
    end: datetime | None = None

