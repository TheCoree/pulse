from pydantic import BaseModel


class EventContentOut(BaseModel):
    id: int
    event_id: int
    order: int
    type: str
    text: str | None = None
    file_url: str | None = None

    model_config = {"from_attributes": True}


class EventContentCreateText(BaseModel):
    text: str
    order: int


class EventContentPatch(BaseModel):
    text: str | None = None
    order: int | None = None
