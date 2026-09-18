import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.session.session_manager import SessionManager


@pytest.mark.asyncio
async def test_watchman_single_task_guarantee():
    mgr = SessionManager()
    mgr._uid = "test_user_123"
    mgr._session_id = "test_session_456"
    mgr._status = "active"

    # Mock StateMonitor.run_loop to just sleep
    with patch("src.watchman.state_monitor.StateMonitor.run_loop", new_callable=AsyncMock) as mock_run_loop:
        mock_run_loop.side_effect = lambda *args, **kwargs: asyncio.sleep(10)

        # Call ensure_watchman_started multiple times sequentially
        await mgr.ensure_watchman_started()
        first_task = mgr._watchman_task
        assert first_task is not None
        assert not first_task.done()

        # Second call should be a no-op and NOT create a duplicate task
        await mgr.ensure_watchman_started()
        assert mgr._watchman_task is first_task
        assert not first_task.done()

        # Cleanup
        mgr.stop_watchman()


@pytest.mark.asyncio
async def test_watchman_concurrent_race_starts():
    """Stress test: 10 concurrent coroutines race to start the watchman loop simultaneously."""
    mgr = SessionManager()
    mgr._uid = "test_user_race"
    mgr._session_id = "test_session_race"
    mgr._status = "active"

    started_loops = 0

    async def slow_run_loop(*args, **kwargs):
        nonlocal started_loops
        started_loops += 1
        await asyncio.sleep(10)

    with patch("src.watchman.state_monitor.StateMonitor.run_loop", side_effect=slow_run_loop):
        # 10 coroutines simultaneously call ensure_watchman_started
        await asyncio.gather(*(mgr.ensure_watchman_started() for _ in range(10)))

        assert mgr._watchman_task is not None
        assert not mgr._watchman_task.done()
        # Strictly only ONE StateMonitor loop should have been spawned
        assert started_loops == 1, f"Expected 1 loop to start under race, got {started_loops}"

        # Cleanup
        mgr.stop_watchman()


@pytest.mark.asyncio
async def test_watchman_crash_recovery():
    """If the active watchman task exits/crashes, ensure_watchman_started cleanly restarts it."""
    mgr = SessionManager()
    mgr._uid = "test_user_crash"
    mgr._session_id = "test_session_crash"
    mgr._status = "active"

    run_count = 0

    async def quick_exit_loop(*args, **kwargs):
        nonlocal run_count
        run_count += 1
        # First run exits immediately (simulating crash/early completion)
        if run_count == 1:
            return
        await asyncio.sleep(10)

    with patch("src.watchman.state_monitor.StateMonitor.run_loop", side_effect=quick_exit_loop):
        await mgr.ensure_watchman_started()
        # Wait for first task to finish
        await asyncio.sleep(0.05)
        assert mgr._watchman_task.done()

        # Next call to ensure_watchman_started detects task is done and spawns a new one
        await mgr.ensure_watchman_started()
        await asyncio.sleep(0.05)
        assert mgr._watchman_task is not None
        assert not mgr._watchman_task.done()
        assert run_count == 2

        # Cleanup
        mgr.stop_watchman()


@pytest.mark.asyncio
async def test_watchman_lifecycle_pause_resume():
    mgr = SessionManager()
    mgr._uid = "test_user_123"
    mgr._session_id = "test_session_456"
    mgr._status = "active"

    with patch("src.watchman.state_monitor.StateMonitor.run_loop", new_callable=AsyncMock) as mock_run_loop:
        mock_run_loop.side_effect = lambda *args, **kwargs: asyncio.sleep(10)
        with patch.object(mgr, "_update_firestore_status", new_callable=AsyncMock):
            await mgr.ensure_watchman_started()

            task = mgr._watchman_task
            assert task is not None and not task.done()

            # Pause session
            await mgr.pause_session()
            assert mgr._status == "paused"
            assert mgr._watchman_task is None or mgr._watchman_task.cancelled() or mgr._watchman_task.done()

            # Resume session
            await mgr.resume_session()
            assert mgr._status == "active"
            assert mgr._watchman_task is not None
            assert not mgr._watchman_task.done()

            # Cleanup
            mgr.stop_watchman()
