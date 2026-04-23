from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtifactFeedbackCreate(BaseModel):
    feedback_type: str
    note: str | None = None


class ArtifactFeedbackListItem(BaseModel):
    id: int
    generated_artifact_id: int
    feedback_type: str
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArtifactFeedbackRead(ArtifactFeedbackListItem):
    pass
