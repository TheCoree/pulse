import os
import uuid
import shutil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_async_session
from core.deps import get_current_user, require_editor
from models.event import Event
from models.event_content import EventContent
from models.user import User
from schemas.event_content import EventContentOut, EventContentCreateText, EventContentPatch

router = APIRouter(
    prefix="/calendars/{calendar_id}/events/{event_id}/content",
    tags=["Event Content"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _get_event_or_404(
    calendar_id: int,
    event_id: int,
    db: AsyncSession,
) -> Event:
    stmt = select(Event).where(
        Event.id == event_id,
        Event.calendar_id == calendar_id,
    )
    event = await db.scalar(stmt)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Событие не найдено")
    return event


# ── GET /content ──────────────────────────────────────────────────────────────
@router.get("", response_model=List[EventContentOut])
async def get_event_content(
    calendar_id: int,
    event_id: int,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(get_current_user),
):
    await _get_event_or_404(calendar_id, event_id, db)

    stmt = (
        select(EventContent)
        .where(EventContent.event_id == event_id)
        .order_by(EventContent.order)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ── POST /content/text ────────────────────────────────────────────────────────
@router.post("/text", response_model=EventContentOut, status_code=status.HTTP_201_CREATED)
async def add_text_block(
    calendar_id: int,
    event_id: int,
    data: EventContentCreateText,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_editor),
):
    await _get_event_or_404(calendar_id, event_id, db)

    block = EventContent(
        event_id=event_id,
        order=data.order,
        type="text",
        text=data.text,
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ── POST /content/upload ──────────────────────────────────────────────────────
@router.post("/upload", response_model=EventContentOut, status_code=status.HTTP_201_CREATED)
async def add_file_block(
    calendar_id: int,
    event_id: int,
    order: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_editor),
):
    await _get_event_or_404(calendar_id, event_id, db)

    # Check file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком велик. Максимальный размер: 50MB"
        )

    ext = os.path.splitext(file.filename or "file.bin")[1] or ".bin"
    # Detect type: image or file
    content_type = file.content_type or ""
    block_type = "image" if content_type.startswith("image/") else "file"

    filename = f"event_{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    block = EventContent(
        event_id=event_id,
        order=order,
        type=block_type,
        file_url=f"/uploads/{filename}",
        text=file.filename if block_type == "file" else None,
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


# ── POST /content/image (alias for backward compatibility) ───────────────────
@router.post("/image", response_model=EventContentOut, status_code=status.HTTP_201_CREATED)
async def add_image_block_legacy(
    calendar_id: int,
    event_id: int,
    order: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_editor),
):
    return await add_file_block(calendar_id, event_id, order, file, db, user)


# ── PATCH /content/{block_id} ─────────────────────────────────────────────────
@router.patch("/{block_id}", response_model=EventContentOut)
async def update_block(
    calendar_id: int,
    event_id: int,
    block_id: int,
    data: EventContentPatch,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_editor),
):
    await _get_event_or_404(calendar_id, event_id, db)

    block = await db.get(EventContent, block_id)
    if not block or block.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Блок не найден")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(block, field, value)

    await db.commit()
    await db.refresh(block)
    return block


# ── DELETE /content/{block_id} ────────────────────────────────────────────────
@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    calendar_id: int,
    event_id: int,
    block_id: int,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_editor),
):
    await _get_event_or_404(calendar_id, event_id, db)

    block = await db.get(EventContent, block_id)
    if not block or block.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Блок не найден")

    # Delete file from disk if it exists
    if block.type in ["image", "file"] and block.file_url:
        filename = block.file_url.split("/")[-1]
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    await db.delete(block)
    await db.commit()
