"""Voice-friendly, bounded plans for the locally consented Windows operator."""
import json
import re
from dataclasses import dataclass

COMMANDS = ("list windows", "inspect window", "confirm window plan", "cancel window plan", "control window", "focus window")
HELP = ('Say "list windows", "focus window 2", or "inspect window". '
        'To act, say "control window click Find then expect Find what then type invoice into Find what". '
        'You can also expand, select, check or uncheck a named control. Say "confirm window plan" to run it.')


class PlanError(ValueError):
    """A plan could not be prepared or safely continued."""


class Unverified(PlanError):
    """A change may already have been dispatched."""


@dataclass(frozen=True)
class Step:
    verb: str
    label: str
    value: str | None = None


def window_instruction(text):
    text = re.sub(r"^(?:hey\s+)?rumi[,.:!]?\s+", "", text.strip(), flags=re.I)
    if text.casefold().startswith("control window "):
        return text
    plain = text.rstrip(".!?").strip()
    lowered = plain.casefold()
    if lowered in COMMANDS or lowered.startswith("focus window "):
        return plain
    return None


def argument(text, limit):
    text = text.strip()
    if text.startswith('"'):
        try:
            text = json.loads(text)
        except ValueError as exc:
            raise PlanError("Use a closing quote around that label or value.") from exc
    if not text or len(text) > limit or any(ord(char) < 32 for char in text):
        raise PlanError("Use a short, single-line label and value.")
    return text


def parse_plan(text):
    # Quotes preserve literal 'then' and 'to' within labels and values.
    if len(text) > 800:
        raise PlanError("Use a shorter plan so Rumi can read it back before you confirm.")
    outside_quotes = r'(?=(?:[^"\\]|\\.|"(?:[^"\\]|\\.)*")*$)'
    tokens = re.split(r'\s+then\s+' + outside_quotes, text, flags=re.I)
    if not 1 <= len(tokens) <= 8:
        raise PlanError("Use up to eight short steps in one plan.")
    steps = []
    for token in tokens:
        match = re.fullmatch(r"(push|click|press|expand|select|type|set|check|uncheck|expect)\s+(.+)", token.strip(), re.I)
        if not match:
            raise PlanError(HELP)
        verb, rest = match[1].lower(), match[2]
        if verb in ("set", "type"):
            separator = "to" if verb == "set" else "into"
            parts = re.split(r'\s+' + separator + r'\s+' + outside_quotes, rest, maxsplit=1, flags=re.I)
            if len(parts) != 2:
                raise PlanError('Say "type [text] into [control name]" or "set [control name] to [text]".')
            label, value = parts if verb == "set" else reversed(parts)
            steps.append(Step("set", argument(label, 120), argument(value, 600)))
        else:
            label = argument(rest, 120)
            if verb == "expect":
                if not steps or steps[-1].verb != "press" or steps[-1].value is not None:
                    raise PlanError('Use "expect" immediately after "press".')
                previous = steps[-1]
                steps[-1] = Step(previous.verb, previous.label, label)
            else:
                steps.append(Step("press" if verb in ("click", "push") else verb, label))
    if not steps or any(step.verb == "press" and not step.value for step in steps):
        raise PlanError('After a press, name the control that should appear: "press Find then expect Find what".')
    return tuple(steps)


class WindowOperator:
    def __init__(self, adapter, clock):
        self.adapter = adapter
        self.clock = clock
        self.pending = None
        self.windows = ()
        self.windows_until = 0
        self.seen = set()

    def claim(self, request_id):
        if request_id in self.seen:
            raise PlanError("That request was already handled. Ask again for a fresh request.")
        if len(self.seen) >= 512:
            raise PlanError("Start a fresh Windows control session.")
        self.seen.add(request_id)

    def run(self, request_id, instruction, guard):
        guard()
        self.claim(request_id)
        command = instruction.casefold()
        if command == "confirm window plan":
            plan, self.pending = self.pending, None
            if not plan or self.clock() >= plan[0]:
                return "clarification", "There is no current Windows plan. Prepare it again."
            _, target, steps = plan
            return self.execute(target, steps, guard)

        # A new operator command replaces any previous unconfirmed plan.
        self.pending = None
        if command == "cancel window plan":
            return "succeeded", "Windows plan cancelled."
        if command == "list windows":
            self.windows = tuple(self.adapter.windows(guard))
            self.windows_until = self.clock() + 60
            lines = [f"{i}. {window.title}" for i, window in enumerate(self.windows, 1)]
            return "succeeded", "Say focus window followed by its number.\n" + ("\n".join(lines) if lines else "No eligible windows found.")
        if command == "focus window" or command.startswith("focus window "):
            index = command.removeprefix("focus window").strip()
            number_words = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
            if index in number_words:
                index = str(number_words.index(index) + 1)
            if not re.fullmatch(r"[1-9][0-9]?", index) or self.clock() >= self.windows_until or int(index) > len(self.windows):
                raise PlanError('Say "list windows", then say the number of the window you want.')
            target = self.windows[int(index) - 1]
            self.adapter.focus(target, guard)
            return "succeeded", f"Focused {target.title}."
        target = self.adapter.foreground(guard)
        if command == "inspect window":
            controls = self.adapter.describe(target, guard)
            return "succeeded", f"{target.title}\n" + ("\n".join(controls) if controls else "No named controls were found.")
        steps = parse_plan(instruction[len("control window "):])
        self.adapter.validate_target(target, guard)
        lines = [f"Plan for {target.title[:100]}."]
        for index, step in enumerate(steps, 1):
            line = f'{index}. {step.verb.capitalize()} "{step.label}"'
            if step.value is not None:
                line += f'{" and look for" if step.verb == "press" else " to"} "{step.value}"'
            lines.append(line)
        lines.append("Within one minute, say Rumi confirm window plan, or Rumi cancel window plan.")
        preview = "\n".join(lines)
        if len(preview) > 700:
            raise PlanError("Use a shorter plan so Rumi can read it back before you confirm.")
        self.pending = self.clock() + 60, target, steps
        return "plan", preview

    def execute(self, target, steps, guard):
        verified = 0
        try:
            for step in steps:
                self.adapter.perform(target, step, guard)
                verified += 1
        except Unverified as exc:
            return "operator_uncertain", f"Verified {verified} of {len(steps)} steps. {exc} Check the window before trying again."
        except PlanError as exc:
            return "clarification", f"Verified {verified} of {len(steps)} steps. {exc}"
        return "succeeded", f"Verified all {verified} steps in {target.title}."
