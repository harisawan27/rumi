"""Voice-friendly, bounded plans for the locally consented Windows operator."""
import json
import re
from dataclasses import dataclass
from .planner import Task, goal_text, matching_controls, natural_task

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


@dataclass(frozen=True)
class PlannedTask:
    task: Task
    verb: str
    label: str = ""


def window_instruction(text):
    text = re.sub(r"^(?:hey\s+)?rumi[,.:!]?\s+", "", text.strip(), flags=re.I)
    if text.casefold().startswith("control window ") or natural_task(text):
        return text
    plain = text.rstrip(".!?").strip()
    lowered = plain.casefold()
    if lowered in COMMANDS or lowered.startswith(("focus window ", "choose option ")):
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
        self.choice = None
        self.task_sheet = None
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
        self.task_sheet = None
        self.claim(request_id)
        command = instruction.casefold()
        if command == "confirm window plan":
            plan, self.pending = self.pending, None
            if not plan or self.clock() >= plan[0]:
                return "clarification", "There is no current Windows plan. Prepare it again."
            _, target, steps = plan
            if isinstance(steps, PlannedTask):
                return self.execute_task(target, steps, guard)
            return self.execute(target, steps, guard)

        # A new operator command replaces any previous unconfirmed plan.
        self.pending = None
        choice, self.choice = self.choice, None
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
        if command.startswith("choose option "):
            number = command.removeprefix("choose option ")
            number = {"one": "1", "two": "2", "three": "3", "four": "4"}.get(number, number)
            if not choice or self.clock() >= choice[0] or not re.fullmatch("[1-4]", number):
                raise PlanError("Ask for the task again to get a fresh list of choices.")
            _, chosen_window, task, offered_verb, offered = choice
            self.adapter.validate_target(chosen_window, guard)
            verb, current = matching_controls(task, self.adapter.controls(chosen_window, guard))
            index = int(number) - 1
            if verb != offered_verb or index >= len(offered) or current.count(offered[index]) != 1:
                raise PlanError("That control is no longer unambiguous. Ask for the task again.")
            return self.stage_task(chosen_window, PlannedTask(task, verb, offered[index]), guard)
        task = natural_task(instruction)
        if task:
            return self.prepare_task(target, task, guard)
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

    def prepare_task(self, target, task, guard):
        if not task.value or len(task.value) > 180 or len(task.name) > 120 or any(ord(char) < 32 for char in task.value + task.name):
            raise PlanError("Use a short, single-line request.")
        if task.kind == "find":
            self.adapter.document(target, guard)
            return self.stage_task(target, PlannedTask(task, "find"), guard)
        verb, labels = matching_controls(task, self.adapter.controls(target, guard))
        if not labels:
            raise PlanError("I couldn't find a matching control. Open the relevant pane or say inspect window.")
        if len(labels) == 1:
            return self.stage_task(target, PlannedTask(task, verb, labels[0]), guard)
        if len(labels) > 4 or len({label.casefold() for label in labels}) != len(labels):
            raise PlanError("Several controls match. Open a smaller pane or name the field you want.")
        self.choice = self.clock() + 60, target, task, verb, labels
        self.task_sheet = self.sheet(target, task, "Which control should I use?", labels)
        options = "\n".join(f"{i}. {label}" for i, label in enumerate(labels, 1))
        return "task_choice", f"Which control should I use?\n{options}\nSay Rumi choose option, followed by its number."

    def stage_task(self, target, plan, guard):
        self.adapter.validate_target(target, guard)
        task, verb, label = plan.task, plan.verb, plan.label
        details = {
            "find": ["Read the document's exposed text and check for a match."],
            "select": [f'Select “{label}” and check that it is selected.'],
            "set": [f'Enter “{task.value}” in “{label}” and read the field back.'],
            "reveal": [f'Open “{label}”.', f'Find the newly visible search field and enter “{task.value}”.'],
        }[verb]
        self.pending = self.clock() + 60, target, plan
        self.task_sheet = self.sheet(target, task, "Ready for your approval", details)
        preview = "\n".join(details)
        return "plan", f"In {target.title[:80]}. {preview}\nSay Rumi confirm window plan or Rumi cancel window plan."

    @staticmethod
    def sheet(target, task, heading, items):
        return {"window": target.title[:120], "goal": goal_text(task), "heading": heading, "items": items}

    def execute_task(self, target, plan, guard):
        task, verb, label = plan.task, plan.verb, plan.label
        try:
            self.adapter.validate_target(target, guard)
            if verb == "find":
                found = self.adapter.find_document_text(target, task.value, guard)
                result = f'Found “{task.value}” in the document.' if found else f'No match for “{task.value}” in the text this document exposes.'
            else:
                current_verb, labels = matching_controls(task, self.adapter.controls(target, guard))
                if verb != current_verb or labels.count(label) != 1:
                    raise PlanError("The planned control changed. Ask me to make a new plan.")
                if verb == "reveal":
                    self.adapter.reveal_search(target, label, guard)
                    _, fields = matching_controls(task, self.adapter.controls(target, guard))
                    # Find the new field from the current UI. Never act on an ambiguous guess.
                    if len(fields) != 1:
                        raise PlanError("Search opened, but I couldn't identify one search field. Say inspect window.")
                    label = fields[0]
                    verb = "set"
                self.adapter.perform(target, Step(verb, label, task.value if verb == "set" else None), guard)
                result = f'Checked that “{label}” contains “{task.value}”.' if verb == "set" else f'Checked that “{label}” is selected.'
        except Unverified as exc:
            return "operator_uncertain", f"{exc} Check the window before trying again."
        except PlanError as exc:
            return "clarification", str(exc)
        self.task_sheet = self.sheet(target, task, "Task checked", [result])
        return "succeeded", result

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
