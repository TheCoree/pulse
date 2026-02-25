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

async def notify_order_confirmed(
    chat_id: int, 
    order_id: int, 
    photo_url: Optional[str] = None, 
    description: Optional[str] = None, 
    reply_to_message_id: Optional[int] = None,
    reply_text: Optional[str] = None,
    reply_photo_urls: Optional[list[str]] = None
) -> Optional[int]:
    """Уведомление о подтверждении админом."""
    base_text = (
        f"<b>Заявка #{order_id} обработана!</b>\n"
        f"📋 Описание: {description or '<i>не указано</i>'}\n"
    )
    
    if reply_text:
        base_text += f"💬 <b>Ответ:</b>\n{reply_text}"
    
    base_text += "\n👍 Пожалуйста, подтвердите исправление..."
    
    reply_markup = {
        "inline_keyboard": [[
            {"text": " Подтверждаю", "callback_data": f"user_confirm_{order_id}"}
        ]]
    }
    
    # Режим отправки фото
    # Отправляем только те фото, которые прикрепил корректор. 
    # Старое фото клиента повторно не шлем (по просьбе пользователя).
    photos_to_send = reply_photo_urls if reply_photo_urls else []

    if photos_to_send:
        # Пытаемся отправить файлы напрямую из файловой системы
        import os
        import json
        
        # Определяем путь к папке uploads относительно текущего файла
        # backend/core/notifications.py -> backend/uploads
        UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
        
        async with httpx.AsyncClient() as client:
            try:
                if len(photos_to_send) > 1:
                    # Media Group - загрузка нескольких файлов
                    files = {}
                    media = []
                    for i, rel_url in enumerate(photos_to_send[:10]):
                        filename = rel_url.split("/")[-1]
                        filepath = os.path.join(UPLOAD_DIR, filename)
                        
                        if os.path.exists(filepath):
                            file_key = f"photo_{i}"
                            with open(filepath, "rb") as f:
                                files[file_key] = (filename, f.read())
                            
                            media_item = {"type": "photo", "media": f"attach://{file_key}"}
                            # Для группы фото используем минимальный заголовок, чтобы не дублировать основной текст
                            if i == 0:
                                media_item["caption"] = f"📸 Фото к исправленной заявке #{order_id}"
                            media.append(media_item)

                    if media:
                        group_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMediaGroup"
                        data = {"chat_id": str(chat_id), "media": json.dumps(media)}
                        if reply_to_message_id:
                            data["reply_parameters"] = json.dumps({"message_id": reply_to_message_id})
                        
                        response = await client.post(group_url, data=data, files=files)
                        if response.status_code != 200:
                            print(f"Error sending MediaGroup: {response.status_code} - {response.text}")
                        
                        # Основной текст и кнопки отправляем ОТДЕЛЬНЫМ сообщением, которое тоже реплаит на оригинал
                        return await send_telegram_notification(chat_id, base_text, reply_markup, reply_to_message_id)
                
                else:
                    # Один файл - sendPhoto с загрузкой файла
                    rel_url = photos_to_send[0]
                    filename = rel_url.split("/")[-1]
                    filepath = os.path.join(UPLOAD_DIR, filename)
                    
                    if os.path.exists(filepath):
                        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
                        data = {
                            "chat_id": str(chat_id),
                            "caption": base_text,
                            "parse_mode": "HTML",
                            "reply_markup": json.dumps(reply_markup)
                        }
                        if reply_to_message_id:
                            data["reply_parameters"] = json.dumps({"message_id": reply_to_message_id})
                        
                        with open(filepath, "rb") as f:
                            files = {"photo": (filename, f.read())}
                            response = await client.post(url, data=data, files=files)
                            
                        if response.status_code == 200:
                            return response.json().get("result", {}).get("message_id")
                        else:
                            print(f"Error sending Photo: {response.status_code} - {response.text}")
                    else:
                        print(f"File not found for direct upload: {filepath}")

            except Exception as e:
                print(f"Exception during direct file upload to Telegram: {e}")

    # Fallback to pure text message with reply
    return await send_telegram_notification(chat_id, base_text, reply_markup, reply_to_message_id)

async def notify_order_rejected(chat_id: int, order_id: int, reply_to_message_id: Optional[int] = None):
    """Уведомление об отклонении."""
    text = f"<b>Заявка #{order_id} отклонена.</b>"
    await send_telegram_notification(chat_id, text, reply_to_message_id=reply_to_message_id)

async def notify_info_requested(chat_id: int, order_id: int, reason: str, reply_to_message_id: Optional[int] = None):
    """Запрос дополнительной информации."""
    text = (
        f"<b>Заявка #{order_id} требует уточнения!</b>\n"
        f"<i>Причина:</i> {reason}\n"
        "⚠️ Вы можете нажать кнопку ниже, чтобы прислать исправленные данные."
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🔄 Изменить заявку", "callback_data": f"user_edit_{order_id}"}
        ]]
    }
    await send_telegram_notification(chat_id, text, reply_markup, reply_to_message_id)
