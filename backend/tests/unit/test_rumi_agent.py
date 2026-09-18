import asyncio
import pytest
from unittest.mock import patch, MagicMock
from src.agent.rumi_agent import (
    generate_intervention,
    get_user_context,
    _current_uid_var,
    _fallback_intervention,
)


@pytest.mark.asyncio
async def test_contextvar_multi_user_isolation():
    """Verify concurrent async tasks maintain strict UID isolation via ContextVar."""
    user_alice_ctx = {"name": "Alice", "projects": [{"name": "Alpha"}]}
    user_bob_ctx = {"name": "Bob", "projects": [{"name": "Beta"}]}

    observed_contexts = {}

    def mock_db_load(uid: str):
        if uid == "user_alice":
            return user_alice_ctx
        elif uid == "user_bob":
            return user_bob_ctx
        return {}

    async def simulate_user_intervention(uid: str):
        with patch("src.memory.firestore_client.get_db") as mock_db:
            doc_mock = MagicMock()
            doc_mock.exists = True
            doc_mock.to_dict.side_effect = lambda: mock_db_load(_current_uid_var.get())
            mock_db.return_value.collection.return_value.document.return_value.get.return_value = doc_mock

            # When fallback executes, it calls get_user_context()
            with patch("src.agent.rumi_agent._get_agent", return_value=None):
                text = await generate_intervention("frustrated", uid, "sess_1")
                observed_contexts[uid] = text

    # Run Alice and Bob concurrently
    await asyncio.gather(
        simulate_user_intervention("user_alice"),
        simulate_user_intervention("user_bob"),
    )

    # Alice got Alice's name, Bob got Bob's name
    assert "Alice" in observed_contexts["user_alice"]
    assert "Bob" in observed_contexts["user_bob"]

    # After execution, the global ContextVar in this runner thread must be reset
    assert _current_uid_var.get() == ""


@pytest.mark.asyncio
async def test_contextvar_finally_reset_on_error():
    """ContextVar token must be reset even if an unhandled exception occurs."""
    with pytest.raises(RuntimeError):
        with patch("src.agent.rumi_agent._get_agent", side_effect=RuntimeError("Boom")):
            await generate_intervention("frustrated", "user_crash", "sess_err")

    # Must be reset to default empty string in finally
    assert _current_uid_var.get() == ""


def test_fallback_intervention_formatting():
    """Fallback intervention formats name and project properly."""
    with patch("src.agent.rumi_agent.get_user_context", return_value={"name": "Zayd", "projects": [{"name": "Rumi"}]}):
        text = _fallback_intervention("coding_block")
        assert "Zayd" in text
        assert "Rumi" in text
