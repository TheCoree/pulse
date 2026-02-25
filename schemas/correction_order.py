from pydantic import BaseModel
from typing import Optional
import datetime


class CorrectionOrderCreate(BaseModel):
    telegram_user_id: int
    telegram_chat_id: int
    telegram_username: Optional[str] = None
    telegram_full_name: Optional[str] = None
    description: Optional[str] = None
    user_message_id: Optional[int] = None


class CorrectionOrderStatusUpdate(BaseModel):
    is_corrected: Optional[bool] = None
    is_reported: Optional[bool] = None
    report_text: Optional[str] = None
    is_rejected: Optional[bool] = None
    is_user_confirmed: Optional[bool] = None
    is_updated: Optional[bool] = None
    bot_message_id: Optional[int] = None


class CorrectionOrderOut(BaseModel):
    id: int
    telegram_user_id: int
    telegram_chat_id: int
    telegram_username: Optional[str]
    telegram_full_name: Optional[str]
    description: Optional[str]
    photo_urls: list[str]
    created_at: datetime.datetime
    is_corrected: bool
    is_reported: bool
    report_text: Optional[str]
    is_rejected: bool
    is_user_confirmed: bool
    is_updated: bool
    bot_message_id: Optional[int]
    user_message_id: Optional[int]
    reply_text: Optional[str] = None
    reply_photo_urls: list[str] = []

    model_config = {"from_attributes": True}
