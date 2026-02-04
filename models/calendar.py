from core.database import Base
from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text

class Calendar(Base):
    __tablename__ = "calendars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    events = relationship("Event", back_populates="calendar")
    
    # ВОТ ЭТОГО НЕ ХВАТАЛО:
    user_links: Mapped[List["CalendarUser"]] = relationship(back_populates="calendar")
