from pydantic import BaseModel, Field
from schemas.auth import GlobalRole

class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: GlobalRole
    is_items_corrector: bool
    telegram_id: int | None = None


    class Config:
        orm_mode = True

class ProfileUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=50)
    username: str | None = Field(
        None, 
        min_length=3, 
        max_length=14, 
        pattern=r"^[a-zA-Z0-9_]+$"
    )

class ChangeUserRole(BaseModel):
    role: GlobalRole

class ChangeUserPermissions(BaseModel):
    is_items_corrector: bool


class ChangePassword(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=25)
    new_password: str = Field(..., min_length=6, max_length=25)