"""Collect résumé facts and review a Word document in a native folder grant."""
import io
import re
import zipfile
from xml.etree import ElementTree as ET

from .contracts import ResumeSave


WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RESUME = r"(?:make|create|write|draft) (?:a |my )?r[eé]sum[eé](?: for me)?"
FOLDER = re.compile(r"(?:make|create) (?:a )?(?:new )?folder (?:in|on) (?:the )?([a-z])(?::|\.?\s+drive) and " + RESUME + r" in it", re.I)
FIELDS = re.compile(r"resume (name|details|folder)(?: (?:is|named))?\s*:?\s+(.+)", re.I | re.S)
CONTROLS = {"confirm resume save", "cancel resume", "polish resume with gemini", "confirm gemini draft", "cancel gemini draft"}


def resume_instruction(text):
    plain = re.sub(r"^(?:hey\s+)?rumi[,.:!]?[ \t]+", "", text.strip(), flags=re.I)
    plain = re.sub(r"^(?:(?:can|could|would) you )?(?:please )?", "", plain, flags=re.I)
    words = plain.rstrip(".!?").strip()
    drive = FOLDER.fullmatch(words)
    if drive:
        return "start", drive[1].upper() + ":"
    if re.fullmatch(RESUME, words, re.I):
        return "start", None
    if words.casefold() in CONTROLS:
        return words.casefold(), None
    field = FIELDS.fullmatch(plain)
    if field:
        value = field[2].strip()
        return field[1].casefold(), value if field[1].lower() == "details" else value.rstrip(".!?")
    if re.match(RESUME + r"(?=\s|$)", words, re.I) or re.match(
            r"(?:make|create) (?:a )?(?:new )?folder\b.*\band " + RESUME + r"(?=\s|$)", words, re.I):
        return "clarify", None
    return None


def render_docx(text):
    """Minimal WordprocessingML package containing exactly the reviewed text."""
    document = ET.Element(f"{{{WORD}}}document")
    body = ET.SubElement(document, f"{{{WORD}}}body")
    for index, line in enumerate(text.split("\n")):
        paragraph = ET.SubElement(body, f"{{{WORD}}}p")
        run = ET.SubElement(paragraph, f"{{{WORD}}}r")
        if index == 0:
            style = ET.SubElement(run, f"{{{WORD}}}rPr")
            ET.SubElement(style, f"{{{WORD}}}b")
            ET.SubElement(style, f"{{{WORD}}}sz", {f"{{{WORD}}}val": "40"})
        for part_index, part in enumerate(line.split("\t")):
            if part_index:
                ET.SubElement(run, f"{{{WORD}}}tab")
            ET.SubElement(run, f"{{{WORD}}}t", {"xml:space": "preserve"}).text = part
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
        archive.writestr("_rels/.rels", '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')
        archive.writestr("word/document.xml", ET.tostring(document, encoding="utf-8", xml_declaration=True))
    return output.getvalue()


class ResumeWorkflow:
    def __init__(self, clock):
        self.clock = clock
        self.seen = set()
        self.cancel()

    def cancel(self):
        self.name = self.details = self.draft = ""
        self.folder = "Resume"
        self.expires = 0
        self.pending_cloud = None

    def run(self, request_id, instruction, root, write, polish, guard):
        guard()
        if request_id in self.seen or len(self.seen) >= 512:
            return "clarification", "This request was already handled or the folder session is full.", {}
        self.seen.add(request_id)
        kind, value = instruction
        if kind == "clarify":
            self.cancel()
            return "clarification", 'Choose your workspace, then say “Rumi, make a résumé”. You can name the new folder after that.', {}
        if kind == "cancel resume":
            self.cancel()
            return "clarification", "Résumé draft discarded.", {}
        if kind == "start":
            self.cancel()
            if value and value.casefold() != root.drive.casefold():
                return "clarification", f"Choose a workspace folder on {value} and ask again. The current folder is {root}.", {}
        elif self.clock() >= self.expires:
            self.cancel()
            return "clarification", "Say Rumi, make a résumé to start a new draft.", {}
        if kind == "confirm gemini draft":
            if not polish or not self.pending_cloud or self.clock() >= self.pending_cloud[1]:
                return "clarification", "Ask to polish the résumé first, then review the text to send.", {}
            source, _ = self.pending_cloud
            self.pending_cloud = None
            try:
                rewritten = polish(source, guard)
                self.draft = ResumeSave(folder=self.folder, text=rewritten).text
            except (ValueError, OSError):
                guard()
                return self.review(root, "Gemini couldn’t polish the draft. Your local draft is ready to review.")
            guard()
            self.expires = self.clock() + 180
            return self.review(root, "Gemini draft ready. Check every detail before saving.")
        self.pending_cloud = None
        if kind == "cancel gemini draft":
            return self.review(root)
        if kind == "confirm resume save":
            if not self.draft:
                return self.review(root)
            action = ResumeSave(folder=self.folder, text=self.draft)
            path = root / action.folder / "Resume.docx"
            self.cancel()
            receipt = write(action)
            if receipt["state"] == "succeeded" and not receipt.get("replayed"):
                return "succeeded", f"Saved and verified {path}", {"path": str(path)}
            if receipt.get("result", {}).get("reason") == "already_exists":
                return "clarification", f"{path.parent} already exists. Start again and choose a new folder name.", {}
            return "operator_uncertain", f"I couldn’t verify the résumé. Check {path} before retrying.", {}
        if kind == "polish resume with gemini":
            if not self.draft or not polish:
                return self.review(root, "Gemini polishing is unavailable. You can save the local draft.")
            self.pending_cloud = (self.draft, min(self.expires, self.clock() + 60))
            return "resume_share", "Review the exact text below. Confirm to send it to Gemini for rewriting.", {"text": self.draft}
        if kind in ("name", "details", "folder"):
            limit = {"name": 120, "details": 6400, "folder": 64}[kind]
            try:
                if not 0 < len(value) <= limit or (kind != "details" and ("\n" in value or "\t" in value)):
                    raise ValueError("invalid field length")
                ResumeSave(folder=value if kind == "folder" else self.folder, text=value)
            except ValueError:
                message = "Use a short folder name with letters, numbers, spaces, hyphens or underscores." if kind == "folder" else "Use shorter, printable résumé details."
                return self.review(root, message)
            setattr(self, kind, value)
            if kind != "folder":
                self.draft = f"{self.name}\n\nExperience, education and skills\n{self.details}" if self.name and self.details else ""
        self.expires = self.clock() + 180
        return self.review(root)

    def review(self, root, message=""):
        path = str(root / self.folder / "Resume.docx")
        if self.draft:
            message = message or "Review your résumé, then say Rumi, confirm resume save."
            return "resume_review", message, {"path": path, "text": self.draft}
        prompt = ('Say “Rumi, resume name” followed by your full name.' if not self.name else
                  'Say “Rumi, resume details” followed by your experience, education and skills.')
        return "resume_details", f"{message} {prompt}".strip(), {"path": path}
