from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int
    role: str
    created_at: datetime
    updated_at: datetime


class ProjectListItem(ProjectRead):
    document_ids: list[int]


class MemberRead(BaseModel):
    project_id: int
    user_id: int
    role: str
    created_at: datetime
