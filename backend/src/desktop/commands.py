"""Conservative local command grammar. File contents never become instructions.

No model, generated code, shell, or invented content. Ambiguous requests require
clarification; one explicit operation per turn. Both speech and typing use this.
"""
import re
from pydantic import TypeAdapter, ValidationError
from .contracts import Action, NamedFile

ACTION = TypeAdapter(Action)
HELP = ('Try "open Notepad", "list files", "read notes.txt", or '
        '"create a file called notes.txt with content: your exact text". '
        'Only one action at a time is supported; files are never overwritten.')


class Clarification(ValueError):
    pass


def _filename(value):
    value = value.strip().strip('"\u201c\u201d')
    if re.search(r'\s+dot\s+(txt|md|csv|json)$', value, re.I):
        value = re.sub(r'\s+dot\s+(txt|md|csv|json)$', lambda m: '.' + m[1].lower(), value, flags=re.I)
        value = re.sub(r'\s+(?:dash|hyphen)\s+', '-', value, flags=re.I)
    if re.search(r'\b(?:and|then)\s+(?:open|read|create|delete|move|launch|run)\b', value, re.I):
        raise Clarification("Please request one computer action at a time.")
    # Speech recognition commonly adds terminal punctuation. Preserve filename
    # spelling and content; do not repair paths, extensions, or device aliases.
    if value.endswith('.') and re.search(r'\.(txt|md|csv|json)\.$', value):
        value = value[:-1]
    try:
        return NamedFile(name=value).name
    except ValidationError as exc:
        raise Clarification("Use a plain .txt, .md, .csv or .json filename in your selected folder.") from exc


def parse_command(text, last_file=None):
    command = text.strip()
    command = re.sub(r'^(?:(?:hey\s+)?rumi[,!]?\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?', '', command, flags=re.I)
    plain = command.rstrip('.!?').strip()
    app = re.fullmatch(r'(?:open|launch|start)\s+(?:the\s+)?(notepad|(?:file\s+)?explorer)(?:\s+please)?', plain, re.I)
    if app:
        return ACTION.validate_python({"operation": "open_app", "app": "notepad" if app[1].lower() == "notepad" else "explorer"})
    if re.fullmatch(r'(?:list|show)(?:\s+me)?\s+(?:the\s+|my\s+)?(?:text\s+)?files(?:\s+(?:in\s+)?(?:this|the|my|selected)\s+folder)?', plain, re.I):
        return ACTION.validate_python({"operation": "list_files"})
    read = re.fullmatch(r'(?:read|show)(?:\s+me)?\s+(?:(?:the|a)\s+)?(?:file\s+)?(.+)', plain, re.I)
    if read:
        target = read[1]
        if target.lower() in ('that file', 'this file', 'it', 'that', 'this'):
            if last_file is None:
                raise Clarification("Which file should I read? Say its full filename first.")
            target = last_file
        return ACTION.validate_python({"operation": "read_text", "name": _filename(target)})
    # The delimiter is explicit. Everything after it is literal file content,
    # including strings such as 'open Explorer' or 'delete all files'.
    create = re.fullmatch(
        r'(?:create|make|save|write)\s+(?:(?:a|the)\s+)?(?:file\s+)?(?:(?:called|named)\s+)?'
        r'(.+?)\s+(?:with\s+(?:these\s+notes|(?:the\s+)?(?:content|text|contents))(?:\s*:\s*|\s+)|containing\s+|with\s+)([\s\S]*)',
        command, re.I)
    if create:
        name, content = _filename(create[1]), create[2]
        if not content.strip() or content.strip().lower().rstrip('.') in ("these notes", "those notes", "the above", "my notes", "this", "that", "text", "content", "contents"):
            raise Clarification("What exact text should I put in the file?")
        try:
            return ACTION.validate_python({"operation": "create_text", "name": name, "text": content})
        except ValidationError as exc:
            raise Clarification("Keep the file content within 16,000 characters.") from exc
    raise Clarification(HELP)
