"""Closed, content-free CREATE diagnostics. No prompts, identities or artifacts."""
import contextvars
import json
import logging
import time
from uuid import UUID

log = logging.getLogger(__name__)
_trace = contextvars.ContextVar("create_trace", default=None)
EVENTS = frozenset({"request_received", "authorization_checked", "active_artifact_loaded",
    "create_planner_invoked", "create_mode_selected", "create_planner_invalid",
    "create_planner_timeout", "create_provider_failed", "artifact_constructed",
    "generated_artifact_created", "generated_artifact_edit_succeeded", "socket_result",
    "voice_acknowledgement_requested", "create_cancelled", "create_failed"})
REASONS = frozenset({"none", "conversation", "artifact", "create", "edit", "invalid",
    "provider", "timeout", "storage", "conflict", "authorization", "superseded"})


def begin(request_id):
    # Only canonical random request IDs may enter diagnostic logs.
    value = UUID(str(request_id))
    if value.version != 4:
        raise ValueError("Invalid request ID")
    return _trace.set((str(value), time.perf_counter()))


def end(token):
    _trace.reset(token)


def emit(event, *, started=None, reason="none"):
    trace = _trace.get()
    if trace is None or event not in EVENTS or reason not in REASONS:
        return
    now = time.perf_counter()
    row = {"event": event, "request_id": trace[0], "elapsed_ms": round((now - trace[1]) * 1000, 3), "reason": reason}
    if started is not None:
        row["duration_ms"] = round(max(0, now - started) * 1000, 3)
    log.info("rumi_create %s", json.dumps(row))
