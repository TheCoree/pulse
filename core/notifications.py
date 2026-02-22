import httpx
from core.config import settings
from typing import Optional

async def send_telegram_notification(chat_id: int, text: str, reply_markup: Optional[dict] = None, reply_to_message_id: Optional[int] = None) -> Optional[int]:
    """Отправляет сообщение пользователю через Telegram Bot API. Возвращает message_id."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("result", {}).get("message_id")
    except Exception as e:
        print(f"Error sending telegram notification: {e}")
        return None

async def delete_telegram_message(chat_id: int, message_id: int):
    """Удаляет сообщение в Telegram."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteMessage"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"chat_id": chat_id, "message_id": message_id})
    except Exception as e:
        print(f"Error deleting telegram message: {e}")

async def notify_order_confirmed(chat_id: int, order_id: int, photo_url: Optional[str] = None, description: Optional[str] = None, reply_to_message_id: Optional[int] = None) -> Optional[int]:
    """Уведомление о подтверждении админом."""
    text = (
        f"<b>Заявка #{order_id} обработана!</b>\n"
        f"📋 Описание: {description or '<i>не указано</i>'}\n"
        "☑️ Пожалуйста, подтвердите исправление..."
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Подтверждаю", "callback_data": f"user_confirm_{order_id}"}
        ]]
    }
    
    # Пытаемся отправить как фото с реплаем
    if photo_url:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
        full_photo_url = f"{settings.FRONTEND_URL}{photo_url}"
        
        payload = {
            "chat_id": chat_id,
            "photo": full_photo_url,
            "caption": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }
        if reply_to_message_id:
            payload["reply_parameters"] = {"message_id": reply_to_message_id}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    return response.json().get("result", {}).get("message_id")
        except:
            pass

    # Fallback to pure text message with reply
    return await send_telegram_notification(chat_id, text, reply_markup, reply_to_message_id)

async def notify_order_rejected(chat_id: int, order_id: int, reply_to_message_id: Optional[int] = None):
    """Уведомление об отклонении."""
    text = f"<b>Заявка #{order_id} отклонена.</b>"
    await send_telegram_notification(chat_id, text, reply_to_message_id=reply_to_message_id)

async def notify_info_requested(chat_id: int, order_id: int, reason: str, reply_to_message_id: Optional[int] = None):
    """Запрос дополнительной информации."""
    text = (
        f"<b>Заявка #{order_id} требует уточнения!</b>\n\n"
        f"<i>Причина:</i> {reason}\n\n"
        "Вы можете нажать кнопку ниже, чтобы прислать исправленные данные."
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🔄 Изменить заявку", "callback_data": f"user_edit_{order_id}"}
        ]]
    }
    await send_telegram_notification(chat_id, text, reply_markup, reply_to_message_id)
