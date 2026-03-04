from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Text, Integer
from core.database import Base


class EventContent(Base):
    __tablename__ = "event_contents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )

    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # "text", "image", or "file"
    type: Mapped[str] = mapped_column(String(10), nullable=False)

    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # e.g. /uploads/event_<uuid>.jpg
    file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    event = relationship("Event", back_populates="contents")
