from pydantic import BaseModel, Field
from typing import List, Optional
from schemas.auth import LocalRole

class CalendarBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: Optional[str] = None

class CalendarCreate(CalendarBase):
    pass

class CalendarUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    type: Optional[str] = None

class ParticipantPublic(BaseModel):
    model_config = {"from_attributes": True}
    
    id: int
    username: str
    display_name: Optional[str] = None
    role: LocalRole

class CalendarPublic(CalendarBase):
    model_config = {"from_attributes": True}
    
    id: int
    role: Optional[LocalRole] = None
    participants: List[ParticipantPublic] = []

class AddUserToCalendar(BaseModel):
    username: str
    role: LocalRole = LocalRole.VIEWER
