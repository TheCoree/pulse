from typing import List
from sqlalchemy import Enum as SQLAlchemyEnum, Text # Добавь или исправь эту строку
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

    # ВОТ ЭТОГО НЕ ХВАТАЛО:
    calendar_links: Mapped[List["CalendarUser"]] = relationship(back_populates="user")