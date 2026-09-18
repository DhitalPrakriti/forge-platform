from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: str
    model: str
    state: str
    failures: int
    open_until: datetime | None
    probe_until: datetime | None
    last_observed_at: datetime | None
    last_error: str | None
