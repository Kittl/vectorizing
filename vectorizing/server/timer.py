"""Collect named timings, including nested processing stages."""

import time


class Timer:
    """Measure nested stages and retain the latest duration for each name."""

    def __init__(self) -> None:
        self.entries = {}
        self.actions_stack = []
        self.time_stack = []

    def start_timer(self, action_name: str) -> None:
        """Start a named stage without ending any enclosing stage."""
        self.time_stack.append(time.time())
        self.actions_stack.append(action_name)

    def end_timer(self) -> None:
        """Record elapsed time for the most recently started stage."""
        self.entries[self.actions_stack.pop()] = time.time() - self.time_stack.pop()

    def timelog(self) -> str:
        """Format recorded stages in insertion order with a trailing separator."""
        log = ""

        for action_name in self.entries:
            time = self.entries[action_name]
            log += f"{action_name}: {time} / "

        return log
