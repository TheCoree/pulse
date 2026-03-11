from datetime import datetime
from typing import List
from sqlalchemy import Enum as SQLAlchemyEnum, Text, Boolean, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
from schemas.auth import GlobalRole

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[GlobalRole] = mapped_column(
        SQLAlchemyEnum(GlobalRole), nullable=False, default=GlobalRole.USER
    )
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_items_corrector: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Telegram & Profile
    display_name: Mapped[str | None] = mapped_column(nullable=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    telegram_connect_token: Mapped[str | None] = mapped_column(nullable=True)
    telegram_connect_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


    calendar_links: Mapped[List["CalendarUser"]] = relationship(back_populates="user")

    refresh_sessions = relationship(
        "RefreshSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )