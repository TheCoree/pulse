from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String
from core.database import Base

class CalendarUser(Base):
    __tablename__ = "calendar_users"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    calendar_id: Mapped[int] = mapped_column(
        ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), default="viewer")

    # relationships
    user = relationship("User", back_populates="calendar_links")
    calendar = relationship("Calendar", back_populates="user_links")
