import asyncio
import pytest

from src.session.voice_session_controller import (
    VoiceSessionController,
    VoiceServerState,
)


def test_initial_state():
    vc = VoiceSessionController()
    assert vc.state == VoiceServerState.IDLE
    assert vc.generation_id == 0
    assert vc.suppress_audio is False
    assert vc.is_generating_or_speaking is False


def test_start_generation_increments_and_suppresses():
    vc = VoiceSessionController()
    gen1 = vc.start_generation("test_query_1")

    assert gen1 == 1
    assert vc.generation_id == 1
    assert vc.state == VoiceServerState.GENERATING
    assert vc.suppress_audio is True
    assert vc.is_generating_or_speaking is True


def test_mark_streaming_unsuppresses_current_generation():
    vc = VoiceSessionController()
    gen1 = vc.start_generation("query_1")

    success = vc.mark_streaming(gen1)
    assert success is True
    assert vc.state == VoiceServerState.STREAMING
    assert vc.suppress_audio is False
    assert vc.is_generating_or_speaking is True


def test_mark_streaming_rejects_stale_generation():
    vc = VoiceSessionController()
    gen1 = vc.start_generation("query_1")
    gen2 = vc.start_generation("query_2")

    # Stale gen1 tries to open streaming gate
    success = vc.mark_streaming(gen1)
    assert success is False
    # State must remain bound to gen2 (GENERATING)
    assert vc.state == VoiceServerState.GENERATING
    assert vc.suppress_audio is True


def test_mark_complete_transitions_to_idle():
    vc = VoiceSessionController()
    gen1 = vc.start_generation("query_1")
    vc.mark_streaming(gen1)

    vc.mark_complete(gen1)
    assert vc.state == VoiceServerState.IDLE
    assert vc.is_generating_or_speaking is False


def test_mark_complete_ignores_stale_generation():
    vc = VoiceSessionController()
    gen1 = vc.start_generation("query_1")
    gen2 = vc.start_generation("query_2")

    # gen1 completes late
    vc.mark_complete(gen1)
    assert vc.state == VoiceServerState.GENERATING
    assert vc.generation_id == gen2


@pytest.mark.asyncio
async def test_cancel_active_generation_cancels_task_and_bumps_generation():
    vc = VoiceSessionController()
    gen1 = vc.start_generation("query_1")

    async def long_running_task():
        await asyncio.sleep(10)

    task = asyncio.create_task(long_running_task())
    vc.set_active_task(task)

    new_gen = vc.cancel_active_generation("user_interrupted")

    assert new_gen == 2
    assert vc.generation_id == 2
    assert vc.state == VoiceServerState.INTERRUPTED
    await asyncio.sleep(0)
    assert task.cancelled() or task.done() or (hasattr(task, "cancelling") and task.cancelling() > 0)


def test_is_stale_helper():
    vc = VoiceSessionController()
    vc.start_generation("query_1")
    current_gen = vc.generation_id

    assert vc.is_stale(current_gen) is False
    assert vc.is_stale(current_gen - 1) is True
    assert vc.is_stale(current_gen + 1) is True
