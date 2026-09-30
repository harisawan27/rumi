"""Run the normal authenticated Rumi app for a local owner-assisted CREATE trial.

No auth/presence overrides, no emulator, no model warm-up. Flags are scoped to
this process. Only content-free CREATE diagnostics go to create-trial-metrics.log.
"""
import argparse
import logging
import os
from pathlib import Path
from dotenv import load_dotenv


def configure():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    for name in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST"):
        if os.getenv(name):
            raise RuntimeError("Real owner trial cannot run with emulator configuration")
    if os.getenv("RUMI_ARTIFACT_PROOF_MODE") == "1":
        raise RuntimeError("Disable proof mode before real owner acceptance")
    os.environ["RUMI_ARTIFACTS_ENABLED"] = "1"
    os.environ["RUMI_CREATE_PLANNER_ENABLED"] = "1"
    credential = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if credential and not Path(credential).is_absolute():
        candidate = root / credential
        if candidate.is_file():
            os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = str(candidate)

    class MetadataOnly(logging.Filter):
        def filter(self, record):
            return record.name in ("src.artifacts.telemetry", "src.artifacts.readiness") and record.getMessage().startswith("rumi_create ")

    handler = logging.FileHandler(root / "backend/create-trial-metrics.log", encoding="utf-8")
    handler.addFilter(MetadataOnly())
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    for name in ("src.artifacts.telemetry", "src.artifacts.readiness"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-trial", action="store_true", required=True)
    parser.parse_args()
    configure()
    import uvicorn
    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, access_log=False)
