from pydantic import BaseModel, EmailStr, Field, ConfigDict

from datetime import datetime

# UserBase
class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(min_length=1, max_length=100)

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_file: str | None
    image_path: str


# PostBase
class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)

class PostCreate(PostBase):
    user_id: int # just TEMPORARY

class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    date_posted: datetime
    author: UserResponse

# ================

# when convert to Java Spring Boot nature, this is DTO
