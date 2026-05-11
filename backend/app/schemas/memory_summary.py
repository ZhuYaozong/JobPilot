from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemorySummaryCreate(BaseModel):
    conversation_id: int
    summary_text: str
    based_on_until_message_id: int


class MemorySummaryUpdate(BaseModel):
    summary_text: str | None = None
    based_on_until_message_id: int | None = None


class MemorySummaryRead(BaseModel):
    id: int
    conversation_id: int
    summary_text: str
    based_on_until_message_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
