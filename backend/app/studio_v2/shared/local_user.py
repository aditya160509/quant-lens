"""Local single-user identity until the new auth ships."""

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    email: str | None = None
    role: str = "authenticated"


async def get_current_user() -> CurrentUser:
    return CurrentUser(id="local")
