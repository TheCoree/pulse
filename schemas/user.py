from pydantic import BaseModel, Field
from schemas.auth import GlobalRole

class UserPublic(BaseModel):
    id: int
    username: str
    role: GlobalRole

    class Config:
        orm_mode = True

class ChangeUserRole(BaseModel):
    role: GlobalRole

class ChangePassword(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=25)
    new_password: str = Field(..., min_length=6, max_length=25)