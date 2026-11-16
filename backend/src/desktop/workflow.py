"""Carry a verified source result into a user-reviewed, immutable note draft."""
import re
from dataclasses import dataclass

from .commands import Clarification, _filename
from .contracts import CreateText
from .operator import PlanError
from .research import ResearchUnavailable


CONFIRM_SAVE = "confirm workflow save"
CANCEL_WORKFLOW = "cancel workflow"
NOTE_REQUEST = r"(?:what you found|(?:the )?(?:search )?results?|it)\s+(?:as|to)\s+(.+)"
DOCUMENT_WORKFLOW = re.compile(
    r"find\s+(.+?)\s+in\s+(?:this|the|my)\s+(?:document|note|file)\s+and\s+save\s+" + NOTE_REQUEST, re.I
)
RESEARCH_WORKFLOW = re.compile(
    r"search\s+(?:the web\s+)?for\s+(.+?)\s+and\s+save\s+(?:the\s+)?first\s+(?:three|3)\s+links"
    r"(?:\s+(?:as|to)\s+(.+))?", re.I
)


@dataclass(frozen=True)
class WorkflowRequest:
    kind: str
    query: str
    filename: str


@dataclass(frozen=True)
class Draft:
    action: CreateText
    source_result: str
    expires: float


def workflow_instruction(text):
    plain = re.sub(r"^(?:hey\s+)?rumi[,.:!]?\s+", "", text.strip(), flags=re.I).rstrip(".!?").strip()
    plain = re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", plain, flags=re.I)
    if plain.casefold() in (CONFIRM_SAVE, CANCEL_WORKFLOW):
        return plain.casefold()
    match = DOCUMENT_WORKFLOW.fullmatch(plain)
    if match:
        return WorkflowRequest("document", match[1], match[2])
    match = RESEARCH_WORKFLOW.fullmatch(plain)
    if match:
        return WorkflowRequest("research", match[1], match[2] or "a note")
    # Keep incomplete compound requests away from the single-window planner.
    lowered = plain.casefold()
    if " and save " in lowered and lowered.startswith(("find ", "search ")):
        raise PlanError('Try “find invoice in this document and save what you found as a note” or “search for accessibility shortcuts and save the first three links”.')
    return None


def note_name(request):
    filename = request.filename.strip()
    if filename.casefold() in {"note", "a note", "text note", "a text note"}:
        return "document-search.txt" if request.kind == "document" else "research-links.txt"
    try:
        filename = _filename(filename)
    except Clarification as exc:
        raise PlanError("Use a plain filename ending in .txt for your note.") from exc
    if not filename.casefold().endswith(".txt"):
        raise PlanError("Use a plain filename ending in .txt for your note.")
    return filename


class Workflow:
    def __init__(self, clock):
        self.clock = clock
        self.draft = None
        self.seen = set()

    def cancel(self):
        self.draft = None

    def run(self, request_id, instruction, document, research, write, guard):
        guard()
        if request_id in self.seen:
            return "clarification", "That workflow request has already been handled.", {}
        if len(self.seen) >= 512:
            raise PlanError("Start a new folder session to run more workflows.")
        self.seen.add(request_id)
        draft = self.draft
        self.cancel()
        if instruction == CANCEL_WORKFLOW:
            return "clarification", "Workflow cancelled. No note was saved by this request.", {}
        if instruction == CONFIRM_SAVE:
            if not draft or self.clock() >= draft.expires:
                return "clarification", "There's no current note to save. Ask for the workflow again.", {}
            guard()
            receipt = write(draft.action)
            if receipt["state"] == "succeeded" and not receipt.get("replayed"):
                return "succeeded", f"Saved and verified {draft.action.name}. {draft.source_result}", {
                    "text": draft.action.text, "name": draft.action.name,
                }
            if receipt.get("result", {}).get("reason") == "already_exists":
                return "clarification", f"{draft.action.name} already exists. Ask again with a different filename.", {}
            return "operator_uncertain", "I couldn't verify the saved note. Check your folder before trying again.", {}

        query = instruction.query.strip().strip('“”"')
        if not query or len(query) > 180 or not query.isprintable():
            raise PlanError("Use a short, single-line search phrase.")
        name = note_name(instruction)
        if instruction.kind == "document":
            source, found = document(query, guard)
            result = (f'Found “{query}” in the text exposed by the document.' if found else
                      f'No match for “{query}” in the text exposed by the document.')
            text = f"Document search\nWindow: {source}\n\n{result}\n"
        else:
            if research is None:
                raise PlanError("Web research is unavailable in this build.")
            try:
                links = research(query, guard)
            except ResearchUnavailable as exc:
                raise PlanError(str(exc)) from exc
            count = f"{len(links)} of the three requested links"
            result = f'Found {count} for “{query}” on DuckDuckGo.'
            entries = "\n\n".join(f"{index}. {link.title}\n{link.url}" for index, link in enumerate(links, 1))
            text = f"Web research from DuckDuckGo\nQuery: {query}\nResults: {count}\n\n{entries}\n"
        guard()
        self.draft = Draft(CreateText(operation="create_text", name=name, text=text), result, self.clock() + 60)
        return "workflow_review", f"{result} Say Rumi, confirm workflow save to create {name}, or say Rumi, cancel workflow.", {
            "text": text, "name": name,
        }
