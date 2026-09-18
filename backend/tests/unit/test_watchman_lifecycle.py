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

        # Call ensure_watchman_started / start_watchman multiple times
        if hasattr(mgr, "ensure_watchman_started"):
            mgr.ensure_watchman_started()
            first_task = mgr._watchman_task
            assert first_task is not None
            assert not first_task.done()

            # Second call should be a no-op and NOT create a duplicate task
            mgr.ensure_watchman_started()
            assert mgr._watchman_task is first_task
            assert not first_task.done()
        else:
            mgr.start_watchman()
            first_task = mgr._watchman_task
            mgr.start_watchman()
            # If start_watchman is naive, it creates a new task and abandons the first
            assert mgr._watchman_task is first_task, "Duplicate watchman task created!"

        # Cleanup
        if hasattr(mgr, "stop_watchman"):
            mgr.stop_watchman()
        elif mgr._watchman_task:
            mgr._watchman_task.cancel()


@pytest.mark.asyncio
async def test_watchman_lifecycle_pause_resume():
    mgr = SessionManager()
    mgr._uid = "test_user_123"
    mgr._session_id = "test_session_456"
    mgr._status = "active"

    with patch("src.watchman.state_monitor.StateMonitor.run_loop", new_callable=AsyncMock) as mock_run_loop:
        mock_run_loop.side_effect = lambda *args, **kwargs: asyncio.sleep(10)
        with patch.object(mgr, "_update_firestore_status", new_callable=AsyncMock):
            if hasattr(mgr, "ensure_watchman_started"):
                mgr.ensure_watchman_started()
            else:
                mgr.start_watchman()

            task = mgr._watchman_task
            assert task is not None and not task.done()

            # Pause session
            await mgr.pause_session()
            assert mgr._status == "paused"
            assert mgr._watchman_task is None or mgr._watchman_task.cancelled() or mgr._watchman_task.done()

            # Resume session
            await mgr.resume_session()
            assert mgr._status == "active"
            # Ensure watchman is running and exactly 1 task exists
            if hasattr(mgr, "ensure_watchman_started"):
                mgr.ensure_watchman_started()
            assert mgr._watchman_task is not None
            assert not mgr._watchman_task.done()

            # Cleanup
            if hasattr(mgr, "stop_watchman"):
                mgr.stop_watchman()
            elif mgr._watchman_task:
                mgr._watchman_task.cancel()
