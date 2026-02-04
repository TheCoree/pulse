from pydantic import BaseModel, Field
from enum import Enum

class GlobalRole(str, Enum):
    ADMIN = "Admin"
    USER = "User"

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=16)
    password: str = Field(..., min_length=6, max_length=32)

class LocalRole(str, Enum):
    EDITOR = "Editor"
    VIEWER = "Viewer"

class Token(BaseModel):
    access_token: str
    refresh_token: str  # Добавили это
    token_type: str

class TokenData(BaseModel):
    username: str | None = None