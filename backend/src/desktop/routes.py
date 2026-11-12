"""Cloud side authorizes only. It never touches the server's files or desktop."""
import os
from fastapi import APIRouter, Depends, HTTPException
from .contracts import Closed
from pydantic import Field
from src.artifacts.access import authorize


class SessionRequest(Closed):
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


def create_router(get_uid, managers):
    router = APIRouter(prefix="/desktop")

    @router.post("/authorize")
    async def authorize_device(body: SessionRequest, uid: str = Depends(get_uid)):
        if os.getenv("RUMI_DESKTOP_ENABLED") != "1":
            raise HTTPException(404, "DESKTOP_UNAVAILABLE")
        await authorize(uid, body.session_id, managers)
        return {"uid": uid, "session_id": body.session_id}

    return router
