from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, DateTime, Text
from core.database import Base
import datetime

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow
    )

    calendar = relationship("Calendar", back_populates="events")
