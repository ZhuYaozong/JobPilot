from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str
    status: str = "active"


class ConversationUpdate(BaseModel):
    title: str | None = None
    status: str | None = None


class ConversationListItem(BaseModel):
    id: int
    title: str
    status: str
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationRead(ConversationListItem):
    pass
