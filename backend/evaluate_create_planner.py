"""Explicit, bounded real-provider evaluation with synthetic requests only.

Run from backend: python evaluate_create_planner.py --live
No Firebase initialization or Firestore operation is permitted by this runner.
"""
import argparse
import asyncio
import json
import statistics
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch
from src.artifacts.contracts import GeneratedArtifact
from src.artifacts.planner import PLAN_ADAPTER, needs_planner, plan_output, provider_for

CASES = [
    ("hello", False, "conversation"),
    ("explain economics", False, "conversation"),
    ("Why do people procrastinate?", False, "conversation"),
    ("Why does spaced repetition work?", False, "conversation"),
    ("What's the best way to track study time?", False, "conversation"),
    ("What is a graph?", True, "conversation"),
    ("Why am I feeling tired after studying?", False, "conversation"),
    ("Explain opportunity cost", False, "conversation"),
    ("Tell me about active recall", False, "conversation"),
    ("How should I organize my revision?", False, "conversation"),
    ("Make me a study tracker for this week", False, "generated_ui:create"),
    ("I need to track how much I study this week", False, "generated_ui:create"),
    ("I need to track my study time", False, "generated_ui:create"),
    ("Create a study tracker for Economics and Physics", False, "generated_ui:create"),
    ("I'd like a study tracker", False, "generated_ui:create"),
    ("Build a study tracker with a daily graph", False, "generated_ui:create"),
    ("Make Economics red", True, "generated_ui:edit"),
    ("Show daily graph", True, "generated_ui:edit"),
    ("Hide the graph", True, "generated_ui:edit"),
    ("Add a graph showing daily study time", True, "generated_ui:edit"),
    ("Make Mathematics blue", True, "generated_ui:edit"),
    ("Change economics to purple", True, "generated_ui:edit"),
    ("Please show me a graph", True, "generated_ui:edit"),
    ("Switch off the daily graph", True, "generated_ui:edit"),
    ("Write a detailed revision plan and put it on Canvas", False, "artifact"),
    ("Give me a long structured comparison of spaced repetition and cramming", False, "artifact"),
    ("Write me a detailed study plan", False, "artifact"),
    ("Write an essay about the causes of inflation", False, "artifact"),
    ("Put this on Canvas: a detailed study schedule", True, "artifact"),
    ("Write a detailed comparison table of these revision methods", False, "artifact"),
    ("Make Economics red", False, "conversation"),
    ("Turn this into a Pomodoro timer with Spotify integration", True, "conversation"),
    ("Create a study tracker for next week", False, "conversation"),
    ("Create a study tracker for 2026-10-01", False, "conversation"),
    ("Create a banking dashboard", False, "conversation"),
    ("Run JavaScript inside this tracker", True, "conversation"),
    ("Make Chemistry red", True, "conversation"),
    ("Delete all my study entries", True, "conversation"),
    ("Actually never mind", True, "conversation"),
    ("What color should I use for Economics?", True, "conversation"),
]


def quantiles(values):
    if not values:
        return {"samples": 0, "p50_ms": None, "p95_ms": None}
    ordered = sorted(values)
    return {"samples": len(values), "p50_ms": round(statistics.median(values), 3),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 3)}


async def evaluate():
    # Fail closed if an accidental import or future refactor tries storage.
    with patch("firebase_admin.initialize_app", side_effect=RuntimeError("no Firebase in planner evaluation")), \
         patch("src.memory.firestore_client.get_db", side_effect=RuntimeError("no storage in planner evaluation")):
        from src.api.main import _make_genai_client, FLASH_MODELS
        import os
        provider = provider_for(_make_genai_client, FLASH_MODELS[0])
        from src.artifacts.planner import prepare_planner_client
        setup_started = time.perf_counter()
        await asyncio.wait_for(prepare_planner_client(_make_genai_client), timeout=60)
        setup_ms = (time.perf_counter() - setup_started) * 1000
        print(f"Provider startup setup: {setup_ms:.1f}ms", flush=True)
        active = GeneratedArtifact.model_validate_json((Path(__file__).resolve().parents[1] / "tests/fixtures/artifacts/valid_study_tracker.json").read_text())
        attempts, invalid, errors = 0, 0, []
        async def measured(context, repair):
            nonlocal attempts, invalid
            attempts += 1
            try:
                raw = await provider(context, repair)
                try:
                    PLAN_ADAPTER.validate_json(raw)
                except Exception:
                    invalid += 1
                return raw
            except Exception as exc:
                errors.append(type(exc).__name__)
                raise
        rows = []
        for index, (text, selected, expected) in enumerate(CASES):
            start = time.perf_counter()
            called = False
            failed = repaired = False
            if "canvas" in text.casefold():
                actual = "artifact"
            elif not needs_planner(text, selected):
                actual = "conversation"
            else:
                called = True
                outcome = await plan_output(text, active if selected else None, selected, date(2026, 9, 14), measured)
                actual = outcome.decision.mode
                if actual == "generated_ui":
                    actual += ":" + outcome.decision.operation
                failed, repaired = outcome.failed, outcome.repaired
            rows.append({"prompt": text, "active": selected, "expected": expected, "actual": actual,
                "provider_called": called, "failed": failed, "repair_used": repaired,
                "correct": actual == expected and not failed, "decision_ms": round((time.perf_counter() - start) * 1000, 3)})
            print(f"{index + 1}/{len(CASES)} {actual} {'PASS' if rows[-1]['correct'] else 'FAIL'}", flush=True)
        report = {"model": os.getenv("RUMI_CREATE_PLANNER_MODEL", FLASH_MODELS[0]),
            "provider": "vertex" if os.getenv("GOOGLE_CLOUD_PROJECT") else "gemini_api",
            "synthetic_only": True, "provider_startup_ms": round(setup_ms, 3),
            "cases": len(rows), "correct": sum(r["correct"] for r in rows),
            "provider_attempts": attempts, "invalid_schema_outputs": invalid,
            "invalid_schema_rate": invalid / attempts if attempts else 0,
            "repair_cases": sum(r["repair_used"] for r in rows),
            "provider_error_types": sorted(set(errors)),
            "inappropriate_ui_cases": sum(r["actual"].startswith("generated_ui") and not r["expected"].startswith("generated_ui") for r in rows),
            "missed_ui_cases": sum(r["expected"].startswith("generated_ui") and r["actual"] != r["expected"] for r in rows),
            "planner_decision": quantiles([r["decision_ms"] for r in rows if r["provider_called"]]),
            "ordinary_fast_path": quantiles([r["decision_ms"] for r in rows if not r["provider_called"] and r["expected"] == "conversation"]),
            "persistence_latency": "measured separately against emulator",
            "interactive_canvas_latency": "requires browser acceptance; not inferred from provider latency", "results": rows}
        destination = Path(__file__).resolve().parents[1] / "docs/create-planner-evaluation.json"
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
        from src.artifacts.planner import close_planner_clients
        await close_planner_clients()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    asyncio.run(evaluate())
