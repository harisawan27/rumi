"""Translate supported everyday goals into bounded Windows control decisions."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Task:
    kind: str
    value: str
    name: str = ""


def natural_task(text):
    text = re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", text, flags=re.I)
    plain = text.rstrip(".?!").strip()
    patterns = (
        ("find", r"find\s+(.+?)\s+in\s+(?:this|the|my)\s+(?:document|note|file)"),
        ("search", r"search\s+for\s+(.+)"),
        ("fill", r"fill\s+(?:the\s+)?(.+?)\s+with\s+(.+)"),
        ("view", r"(?:switch|change)\s+to\s+(?:the\s+)?(.+?)\s+(?:view|tab)"),
    )
    for kind, pattern in patterns:
        match = re.fullmatch(pattern, text if kind == "fill" else plain, re.I)
        if match:
            if kind == "fill":
                return Task(kind, match[2].strip(), match[1].strip())
            return Task(kind, match[1].strip().strip('“”"'))
    return None


SEARCH_FIELDS = frozenset({"find", "find what", "find text", "search", "search box", "search field", "search query", "search text"})
SEARCH_BUTTONS = frozenset({"find", "show find", "find in document", "find in page", "show search", "open search", "search"})
SELECTABLE = frozenset({"tabitem", "listitem", "radiobutton", "treeitem"})


def matching_controls(task, controls):
    """Return viable choices, in the order exposed by the app."""
    eligible = [(label, kind) for label, kind in controls if label and kind]
    if task.kind == "fill":
        names = {task.name.casefold()}
        names.add(task.name.removesuffix(" field").casefold())
        return "set", [name for name, kind in eligible if kind == "edit" and name.casefold() in names]
    if task.kind == "view":
        value = task.value.casefold()
        names = {value, f"{value} view", f"{value} tab"}
        return "select", [name for name, kind in eligible if kind in SELECTABLE and name.casefold() in names]
    fields = [name for name, kind in eligible if kind == "edit" and name.casefold() in SEARCH_FIELDS]
    if fields:
        return "set", fields
    return "reveal", [name for name, kind in eligible if kind in {"button", "menuitem"} and name.casefold() in SEARCH_BUTTONS]


def goal_text(task):
    if task.kind == "find":
        return f'Find “{task.value}” in this document'
    if task.kind == "search":
        return f'Search for “{task.value}”'
    if task.kind == "fill":
        return f'Fill {task.name} with “{task.value}”'
    return f'Switch to {task.value}'
