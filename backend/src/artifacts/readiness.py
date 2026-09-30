"""Capability readiness, not a substitute for owner authorization or a cloud probe."""
import asyncio
import logging
import os
import re

log = logging.getLogger(__name__)


class CreateReadiness:
    def __init__(self):
        self.provider = "not_checked"
        self.storage = "not_checked"
        self.task = None

    def snapshot(self):
        enabled = os.getenv("RUMI_CREATE_PLANNER_ENABLED") == "1" and os.getenv("RUMI_ARTIFACTS_ENABLED") == "1"
        return {"enabled": enabled, "provider": self.provider, "storage": self.storage,
                "status": "disabled" if not enabled else "degraded" if "unavailable" in (self.provider, self.storage) else "configured"}

    async def prepare(self, factory):
        from .planner import prepare_planner_client
        model = os.getenv("RUMI_CREATE_PLANNER_MODEL")
        if model is not None and not re.fullmatch(r"[A-Za-z0-9_./:-]{1,160}", model):
            self.provider = "unavailable"
            log.warning("rumi_create readiness reason=invalid_configuration")
            return
        try:
            await asyncio.wait_for(prepare_planner_client(factory), timeout=12)
            self.provider = "client_initialized"  # Does NOT claim provider/network health.
        except Exception:
            self.provider = "unavailable"
            log.warning("rumi_create readiness reason=provider_setup")

    def start(self, factory):
        self.provider = self.storage = "not_checked"
        enabled = self.snapshot()["enabled"]
        log.info("rumi_create configuration enabled=%s restart_required=true", str(enabled).lower())
        if enabled:
            self.task = asyncio.create_task(self.prepare(factory))

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None


readiness = CreateReadiness()
