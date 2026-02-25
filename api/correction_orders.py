import os
import uuid
import shutil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_async_session
from core.config import settings
from core.deps import get_current_user, require_items_corrector
from models.correction_order import CorrectionOrder
from models.user import User
from schemas.correction_order import CorrectionOrderOut, CorrectionOrderStatusUpdate
from core.notifications import notify_order_confirmed, notify_order_rejected, notify_info_requested

router = APIRouter(prefix="/correction-orders", tags=["Correction Orders"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _verify_bot_secret(x_bot_secret: str = Header(...)):
    """Проверяет секретный заголовок от бота."""
    if x_bot_secret != settings.BOT_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный секретный ключ бота",
        )


# ── POST /correction-orders/ ──────────────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CorrectionOrderOut)
async def create_correction_order(
    telegram_user_id: int = Form(...),
    telegram_chat_id: int = Form(...),
    telegram_username: str | None = Form(None),
    telegram_full_name: str | None = Form(None),
    description: str | None = Form(None),
    replace_order_id: int | None = Form(None),
    user_message_id: int | None = Form(None),
    photos: List[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_async_session),
    _: None = Depends(_verify_bot_secret),
):
    # Если указан ID для замены, обновляем существующую заявку
    if replace_order_id:
        order = await db.get(CorrectionOrder, replace_order_id)
        if order and order.telegram_user_id == telegram_user_id:
            # Удаляем старые файлы
            for photo_url in (order.photo_urls or []):
                filename = photo_url.split("/")[-1]
                filepath = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except: pass
            
            # Сохраняем новые файлы
            photo_urls: list[str] = []
            for photo in photos:
                ext = os.path.splitext(photo.filename or "photo.jpg")[1] or ".jpg"
                filename = f"{uuid.uuid4()}{ext}"
                filepath = os.path.join(UPLOAD_DIR, filename)
                with open(filepath, "wb") as f:
                    shutil.copyfileobj(photo.file, f)
                photo_urls.append(f"/uploads/{filename}")

            # Обновляем поля
            order.description = description
            order.photo_urls = photo_urls
            order.is_updated = True
            if user_message_id:
                order.user_message_id = user_message_id
            # Сбрасываем статусы, чтобы админ проверил заново
            order.is_corrected = False
            order.is_reported = False
            order.is_rejected = False
            order.is_user_confirmed = False
            
            await db.commit()
            await db.refresh(order)
            return order

    # Сохраняем каждый файл
    photo_urls: list[str] = []
    for photo in photos:
        ext = os.path.splitext(photo.filename or "photo.jpg")[1] or ".jpg"
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_urls.append(f"/uploads/{filename}")

    order = CorrectionOrder(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        telegram_username=telegram_username,
        telegram_full_name=telegram_full_name,
        description=description,
        photo_urls=photo_urls,
        user_message_id=user_message_id,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


# ── GET /correction-orders/ ───────────────────────────────────────────────────
@router.get("/")
async def list_correction_orders(
    skip: int = 0,
    limit: int = 10,
    status_filter: str = "all",
    status: str | None = None, # Алиас для фронтенда
    sort: str = "newest",
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    # Базовые запросы
    count_stmt = select(func.count()).select_from(CorrectionOrder)
    stmt = select(CorrectionOrder)

    # Обработка алиаса
    s_filter = status or status_filter

    # Применяем фильтрацию по статусу
    if s_filter == "new":
        filters = (CorrectionOrder.is_corrected == False) & (CorrectionOrder.is_rejected == False) & (CorrectionOrder.is_reported == False)
        count_stmt = count_stmt.where(filters)
        stmt = stmt.where(filters)
    elif s_filter == "corrected":
        filters = (CorrectionOrder.is_corrected == True)
        count_stmt = count_stmt.where(filters)
        stmt = stmt.where(filters)
    elif s_filter == "problematic":
        filters = (CorrectionOrder.is_rejected == True) | (CorrectionOrder.is_reported == True)
        count_stmt = count_stmt.where(filters)
        stmt = stmt.where(filters)

    # Получаем общее количество после фильтрации
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one()

    # Применяем сортировку
    if sort == "oldest":
        stmt = stmt.order_by(CorrectionOrder.created_at.asc())
    else:
        stmt = stmt.order_by(CorrectionOrder.created_at.desc())

    # Применяем пагинацию
    stmt = stmt.offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    orders = result.scalars().all()

    return {
        "items": orders,
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ── PATCH /correction-orders/{id} ─────────────────────────────────────────────
@router.patch("/{order_id}", response_model=CorrectionOrderOut)
async def update_correction_order(
    order_id: int,
    is_corrected: bool | None = Form(None),
    is_reported: bool | None = Form(None),
    report_text: str | None = Form(None),
    is_rejected: bool | None = Form(None),
    is_user_confirmed: bool | None = Form(None),
    is_updated: bool | None = Form(None),
    bot_message_id: int | None = Form(None),
    reply_text: str | None = Form(None),
    reply_photos: List[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_async_session),
    corrector: User = Depends(require_items_corrector),
):
    order = await db.get(CorrectionOrder, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")

    # Сохраняем старые статусы для сравнения
    prev_corrected = order.is_corrected
    prev_rejected = order.is_rejected
    prev_reported = order.is_reported

    # Запрет отмены статуса "Готово", если пользователь уже подтвердил
    if prev_corrected and is_corrected is False and order.is_user_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отменить готовность, так как пользователь уже подтвердил наличие"
        )

    # Применяем изменения
    if is_corrected is not None: order.is_corrected = is_corrected
    if is_reported is not None: order.is_reported = is_reported
    if report_text is not None: order.report_text = report_text
    if is_rejected is not None: order.is_rejected = is_rejected
    if is_user_confirmed is not None: order.is_user_confirmed = is_user_confirmed
    if is_updated is not None: order.is_updated = is_updated
    if bot_message_id is not None: order.bot_message_id = bot_message_id
    if reply_text is not None: order.reply_text = reply_text

    # Обработка новых фото для ответа
    if reply_photos:
        # Если присланы новые фото, заменяем старые (опционально, но по логике заявки так)
        # В данном случае просто добавляем или заменяем
        new_reply_urls: list[str] = []
        for photo in reply_photos:
            ext = os.path.splitext(photo.filename or "photo.jpg")[1] or ".jpg"
            filename = f"reply_{uuid.uuid4()}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                shutil.copyfileobj(photo.file, f)
            new_reply_urls.append(f"/uploads/{filename}")
        order.reply_photo_urls = new_reply_urls

    await db.commit()
    await db.refresh(order)

    # Уведомления при смене статуса
    if not prev_corrected and order.is_corrected:
        # Уведомление о подтверждении (с возможным текстом и фото ответа)
        msg_id = await notify_order_confirmed(
            order.telegram_chat_id, 
            order.id, 
            photo_url=order.photo_urls[0] if order.photo_urls else None, 
            description=order.description,
            reply_to_message_id=order.user_message_id,
            reply_text=order.reply_text,
            reply_photo_urls=order.reply_photo_urls
        )
        if msg_id:
            order.bot_message_id = msg_id
            await db.commit()
            await db.refresh(order)
            
    elif prev_corrected and not order.is_corrected:
        # Если админ отменил "Готово", удаляем старое сообщение с кнопкой у пользователя
        if order.bot_message_id:
            from core.notifications import delete_telegram_message
            await delete_telegram_message(order.telegram_chat_id, order.bot_message_id)
            order.bot_message_id = None
        
        # Очищаем данные ответа
        order.reply_text = None
        # Удаляем файлы фото ответа
        for url in (order.reply_photo_urls or []):
            filename = url.split("/")[-1]
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass
        order.reply_photo_urls = []
        await db.commit()
        await db.refresh(order)

    elif not prev_rejected and order.is_rejected:
        await notify_order_rejected(order.telegram_chat_id, order.id, reply_to_message_id=order.user_message_id)
    elif not prev_reported and order.is_reported:
        await notify_info_requested(order.telegram_chat_id, order.id, order.report_text or "Не указана", reply_to_message_id=order.user_message_id)

    return order


# ── POST /correction-orders/confirm/{id} ──────────────────────────────────────
@router.post("/{order_id}/user-confirm", response_model=CorrectionOrderOut)
async def user_confirm_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session),
    _: None = Depends(_verify_bot_secret),
):
    """Эндпоинт для бота: подтверждение от пользователя."""
    order = await db.get(CorrectionOrder, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    
    if not order.is_corrected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Вы не можете подтвердить наличие, пока администратор не проверил заявку"
        )
    
    order.is_user_confirmed = True
    await db.commit()
    await db.refresh(order)
    return order


# ── DELETE /correction-orders/{order_id} ──────────────────────────────────────
@router.delete("/{order_id}")
async def delete_correction_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session),
    corrector: User = Depends(require_items_corrector),
):
    order = await db.get(CorrectionOrder, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    
    # Удаляем фото из папки uploads
    for photo_url in (order.photo_urls or []):
        filename = photo_url.split("/")[-1]
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error removing file {filepath}: {e}")

    await db.delete(order)
    await db.commit()
    return {"detail": "Заявка успешно удалена"}
