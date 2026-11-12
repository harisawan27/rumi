"""Speak a bounded client-reported receipt; never execute or interpret file data."""
import asyncio
import os
import time
from typing import Literal
from fastapi import HTTPException
from .contracts import RequestIdentity
from src.artifacts.access import authorize


class ReceiptNotice(RequestIdentity):
    state: Literal["succeeded", "dispatched", "uncertain", "failed", "clarification"]
    operation: Literal["list_files", "read_text", "create_text", "open_app"] | None = None


def speech_for(receipt):
    if receipt.state == "uncertain":
        return "The action may have completed. Check your folder or app before trying again."
    if receipt.state == "clarification":
        return "I need a more specific computer request. Check the computer panel for details."
    if receipt.state == "dispatched" and receipt.operation == "open_app":
        return "The app launch was requested. Please check that its window opened."
    if receipt.state == "succeeded":
        return {"create_text": "Your file was created and its contents verified.",
                "read_text": "The file contents are in the computer panel.",
                "list_files": "The file list is in the computer panel."}.get(receipt.operation,
                    "I could not verify the result. Check your computer before trying again.")
    return "I could not complete that computer action. Check the computer panel."


async def acknowledge(uid, session_id, manager, managers, raw):
    if os.getenv("RUMI_DESKTOP_ENABLED") != "1":
        raise HTTPException(404, "DESKTOP_UNAVAILABLE")
    notice = ReceiptNotice.model_validate(raw)
    if notice.session_id != session_id or not time.time() < notice.expires_at <= time.time() + 120:
        raise HTTPException(403, "DESKTOP_NOTICE_EXPIRED")
    await authorize(uid, session_id, managers)
    seen = getattr(manager, "_desktop_spoken_receipts", None)
    if seen is None:
        seen = manager._desktop_spoken_receipts = {}
    for request_id, expires_at in list(seen.items()):
        if expires_at <= time.time():
            del seen[request_id]
    if notice.request_id in seen:
        return
    if len(seen) >= 128:
        raise HTTPException(429, "DESKTOP_ACK_BUSY")
    seen[notice.request_id] = notice.expires_at
    manager.interrupt_audio("desktop_receipt")
    async def speak():
        await authorize(uid, session_id, managers)
        if time.time() >= notice.expires_at:
            return
        await manager.voice_query(
            "Read exactly this single acknowledgement of the local helper's report. "
            "Do not add advice, questions, claims of window focus, or other actions: " + speech_for(notice),
            desktop_request_id=notice.request_id)
    async def guarded():
        try:
            await speak()
        except (HTTPException, asyncio.CancelledError):
            pass
        except Exception:
            # Voice availability cannot turn a receipt into another execution.
            # The local result remains visible; do not retry or expose its data.
            pass
    manager._speak_task = asyncio.create_task(guarded())
