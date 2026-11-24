from typing import Literal

from pydantic import BaseModel

PartStatus = Literal["ok", "error"]
MlStatus = Literal["ok", "loading", "error"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    db: PartStatus
    ml: MlStatus
