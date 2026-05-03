from pydantic import BaseModel,EmailStr,ConfigDict,Field
from pydantic.types import UUID4
from datetime import datetime
from typing import Optional
from src.models.user import SkillLevel

class UserBase(BaseModel):
    email: EmailStr
    display_name : str= Field(...,min_length=2,max_length=50)
    skill_level: SkillLevel = SkillLevel.BEGINNER

class UserCreate(UserBase):
    pass