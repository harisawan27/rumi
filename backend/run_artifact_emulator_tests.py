"""Explicit entrypoint: never imports ordinary tests or weakens their guards."""
import sys
from pathlib import Path
from src.artifacts.emulator import require_emulator

if __name__ == "__main__":
    require_emulator()  # fails before collection, client construction or credentials
    import pytest
    raise SystemExit(pytest.main([str(Path(__file__).parent / "emulator_tests"),
                                 "--run-artifact-emulator", *sys.argv[1:]]))
