"""Pure state transitions; camera, BLE and display details stay outside this module."""
from dataclasses import dataclass
import math
import time
from .command_handler import Command


@dataclass(frozen=True)
class Snapshot:
    pages: tuple[str, ...]
    index: int
    entered: bool
    received_count: int
    confirmations: int
    last_command: str
    focus_active: bool
    timer_state: str
    timer_minutes_left: int
    revision: int

    @property
    def page(self):
        return self.pages[self.index]


class UIState:
    def __init__(self, pages=("home", "focus", "timer", "status"), timer_minutes=25, clock=time.monotonic):
        if not pages or len(set(pages)) != len(pages):
            raise ValueError("Pages must be nonempty and distinct")
        if timer_minutes <= 0:
            raise ValueError("Timer duration must be positive")
        self.pages = tuple(pages)
        self.timer_duration = timer_minutes * 60
        self.clock = clock
        self.index = 0
        self.entered = False
        self.received_count = 0
        self.confirmations = 0
        self.last_command = "—"
        self.focus_active = False
        self.timer_state = "ready"
        self.timer_remaining = float(self.timer_duration)
        self.timer_deadline = None
        self.revision = 0
        self.last_timer_minutes = timer_minutes

    def _remaining(self):
        if self.timer_deadline is not None:
            return max(0.0, self.timer_deadline - self.clock())
        return self.timer_remaining

    def _update_timer(self):
        if self.timer_deadline is not None and self._remaining() <= 0:
            self.timer_deadline = None
            self.timer_remaining = 0
            self.timer_state = "done"
            return True
        return False

    def _confirm_timer(self):
        if self.timer_state == "running":
            self.timer_remaining = self._remaining()
            self.timer_deadline = None
            self.timer_state = "paused"
        else:
            if self.timer_state in {"ready", "done"}:
                self.timer_remaining = float(self.timer_duration)
            self.timer_deadline = self.clock() + self.timer_remaining
            self.timer_state = "running"

    def apply(self, command):
        if not isinstance(command, Command):
            raise ValueError("UIState requires a parsed Command")
        self._update_timer()
        self.received_count += 1
        self.last_command = command.value
        if command is Command.CW:
            self.index = (self.index + 1) % len(self.pages)
            self.entered = False
        elif command is Command.CCW:
            if self.entered:
                self.entered = False
            else:
                self.index = (self.index - 1) % len(self.pages)
        elif not self.entered:
            self.entered = True
        else:
            self.confirmations += 1
            if self.pages[self.index] == "focus":
                self.focus_active = not self.focus_active
            elif self.pages[self.index] == "timer":
                self._confirm_timer()
        self.revision += 1
        self.last_timer_minutes = math.ceil(self._remaining() / 60)
        return self.snapshot()

    def tick(self):
        completed = self._update_timer()
        minutes = math.ceil(self._remaining() / 60)
        changed = completed or (self.pages[self.index] == "timer" and minutes != self.last_timer_minutes)
        self.last_timer_minutes = minutes
        if changed:
            self.revision += 1
        return self.snapshot() if changed else None

    def snapshot(self):
        return Snapshot(self.pages, self.index, self.entered, self.received_count, self.confirmations,
                        self.last_command, self.focus_active, self.timer_state,
                        math.ceil(self._remaining() / 60), self.revision)
