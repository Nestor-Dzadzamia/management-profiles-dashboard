from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: int
    project_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by_id: int | None
    created_at: datetime
    updated_at: datetime
