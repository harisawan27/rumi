"""Cross-capability workflow regressions. Unit tests never call the network."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import quote
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from src.desktop.native_runtime import NativeRuntime
from src.desktop.research import ResearchUnavailable, ResultLinks, SearchLink


FIND = "Rumi find invoice in this document and save what you found as a note"
SEARCH = "Rumi search for Windows accessibility shortcuts and save the first three links"
CONFIRM = "confirm workflow save"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        data = tempfile.TemporaryDirectory()
        self.addCleanup(data.cleanup)
        self.root = Path(data.name) / "notes"
        self.root.mkdir()
        self.clock = 100.0
        self.document = Mock()
        self.document.foreground.return_value = SimpleNamespace(title="Invoice editor")
        self.document.find_document_text.return_value = True
        self.results = tuple(SearchLink(f"Link {i}", f"https://example.org/{i}") for i in range(3))
        self.research = Mock(return_value=self.results)
        self.runtime = NativeRuntime(Path(data.name) / "receipts.db", desktop_check=Mock(),
                                     clock=lambda: self.clock, wall_clock=lambda: self.clock,
                                     operator_factory=lambda: self.document, research=self.research)
        self.addCleanup(self.runtime.close)
        self.runtime.enable(self.root, self.runtime.generation)

    def send(self, text, request_id=None):
        return self.runtime.command({
            "request_id": request_id or str(uuid4()),
            "session_id": self.runtime.status()["session_id"] or "missing",
            "expires_at": int(self.clock) + 90,
            "text": text,
        })

    def test_document_requires_both_permissions_and_saves_only_verified_match(self):
        rejected = self.send(FIND)
        self.assertIn("Enable Windows control", rejected["message"])
        self.document.find_document_text.assert_not_called()
        self.runtime.enable_operator(self.runtime.generation)
        draft = self.send(FIND)
        self.assertEqual(draft["state"], "workflow_review")
        self.assertEqual(list(self.root.iterdir()), [])
        self.document.find_document_text.return_value = False  # Save exactly what was reviewed.
        receipt = self.send(CONFIRM)
        self.assertEqual(receipt["state"], "succeeded")
        content = (self.root / "document-search.txt").read_bytes().decode()
        self.assertEqual(content, draft["result"]["text"])
        self.assertIn("Found", content)
        self.assertIn("Invoice editor", content)
        self.document.find_document_text.assert_called_once()
        self.research.assert_not_called()
        self.assertEqual(self.send("read that file")["result"]["text"], content)

    def test_online_query_only_then_verify_ordered_links_and_replay(self):
        preview = self.send(SEARCH)
        self.assertEqual(preview["state"], "workflow_review")
        self.assertEqual(self.research.call_args.args[0], "Windows accessibility shortcuts")
        self.assertEqual(list(self.root.iterdir()), [])
        approval = str(uuid4())
        self.assertEqual(self.send(CONFIRM, approval)["state"], "succeeded")
        note = self.root / "research-links.txt"
        text = note.read_bytes().decode()
        self.assertEqual(text, preview["result"]["text"])
        self.assertEqual([text.index(link.url) for link in self.results], sorted(text.index(link.url) for link in self.results))
        self.assertEqual(self.send(SEARCH + " as new-links.txt")["state"], "workflow_review")
        self.assertEqual(self.send(CONFIRM, approval)["state"], "clarification")
        self.assertFalse((self.root / "new-links.txt").exists())

    def test_cancel_expiry_and_other_commands_invalidate_the_draft(self):
        for interruption in ("cancel workflow", "expiry", "list files"):
            self.assertEqual(self.send(SEARCH)["state"], "workflow_review")
            if interruption == "expiry":
                self.clock += 61
            else:
                self.send(interruption)
            self.assertEqual(self.send(CONFIRM)["state"], "clarification")
            self.assertEqual(list(self.root.iterdir()), [])

    def test_collision_malformed_filename_and_network_error_do_not_write(self):
        self.assertEqual(self.send(SEARCH + " as ../private.txt")["state"], "clarification")
        self.research.assert_not_called()
        existing = self.root / "research-links.txt"
        existing.write_text("keep me")
        self.send(SEARCH)
        self.assertIn("already exists", self.send(CONFIRM)["message"])
        self.assertEqual(existing.read_text(), "keep me")
        self.research.side_effect = ResearchUnavailable("No result links returned.")
        self.assertEqual(self.send(SEARCH)["state"], "clarification")
        self.assertEqual(self.send(CONFIRM)["state"], "clarification")
        self.assertEqual(list(self.root.iterdir()), [existing])

    def test_stop_during_research_discards_the_result_and_cannot_save(self):
        started, release, responses = threading.Event(), threading.Event(), []

        def blocked(query, guard):
            started.set()
            release.wait(3)
            guard()
            return self.results

        self.research.side_effect = blocked
        worker = threading.Thread(target=lambda: responses.append(self.send(SEARCH)))
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            self.runtime.stop()
        finally:
            release.set()
            worker.join(4)
        self.assertEqual(responses[0]["state"], "blocked")
        self.runtime.enable(self.root, self.runtime.generation)
        self.assertEqual(self.send(CONFIRM)["state"], "clarification")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_research_uses_distinct_https_organic_links_in_page_order(self):
        parser = ResultLinks()
        url = "https://example.org/one"
        parser.feed(
            f'<a class="result__a" href="//duckduckgo.com/l/?uddg={quote(url, safe="")}">A &amp; <b>B</b></a>'
            f'<a class="result__a" href="{url}">Duplicate</a>'
            '<a class="result__a" href="javascript:evil()">Script</a>'
            '<a class="result__a result__a--ad" href="https://example.org/ad">Ad</a>'
            '<a class="result__a" href="https://example.org/two">Second</a>'
            '<a class="result__a" href="https://example.org/three">Third</a>'
            '<a class="result__a" href="https://example.org/four">Fourth</a>'
        )
        self.assertEqual(parser.results, [SearchLink("A & B", url),
            SearchLink("Second", "https://example.org/two"), SearchLink("Third", "https://example.org/three")])


if __name__ == "__main__":
    unittest.main()
