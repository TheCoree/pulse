from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, JSON, DateTime, BigInteger, Boolean
from core.database import Base
import datetime


class CorrectionOrder(Base):
    __tablename__ = "correction_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Telegram-данные отправителя
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_full_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Содержимое заявки
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Метаданные
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    # Статусные флаги
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_reported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Список ID сообщений в боте (например, MediaGroup + основное сообщение с кнопками)
    bot_message_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    
    # Флаг, что заявка была обновлена пользователем
    is_updated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ID сообщения пользователя, на которое нужно будет отвечать (Reply)
    user_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Ответ администратора (корректора) при подтверждении
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_photo_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
