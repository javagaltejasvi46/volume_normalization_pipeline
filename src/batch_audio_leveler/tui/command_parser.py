"""Command input parsing and session history for Textual command bar."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ParsedCommand:
    action: str
    args: List[str]
    raw: str


class CommandParserError(Exception):
    pass


def parse_command_line(line: str) -> Optional[ParsedCommand]:
    """Parse a single command line string into action and arguments.

    Handles quotes, Windows backslashes, and extra spaces safely.
    """
    text = line.strip()
    if not text:
        return None

    # Handle leading slash or colon (e.g. /help, :quit)
    if text.startswith(("/", ":")):
        text = text[1:].strip()

    if not text:
        return None

    try:
        # Use posix=False on Windows or manual split to preserve backslashes in paths
        parts = shlex.split(text, posix=False)
    except ValueError:
        # If quoting is mismatched, fallback to simple whitespace split
        parts = text.split()

    clean_parts: List[str] = []
    for p in parts:
        p_clean = p.strip()
        if (p_clean.startswith('"') and p_clean.endswith('"')) or (p_clean.startswith("'") and p_clean.endswith("'")):
            p_clean = p_clean[1:-1]
        clean_parts.append(p_clean)

    if not clean_parts:
        return None

    action = clean_parts[0].lower()
    args = clean_parts[1:]
    return ParsedCommand(action=action, args=args, raw=line)


class CommandHistory:
    """Session-only command history for Up/Down arrow navigation."""

    def __init__(self, max_size: int = 50) -> None:
        self.max_size = max_size
        self._history: List[str] = []
        self._cursor: int = 0

    def add(self, cmd: str) -> None:
        cmd = cmd.strip()
        if not cmd:
            return
        if self._history and self._history[-1] == cmd:
            self._cursor = len(self._history)
            return
        self._history.append(cmd)
        if len(self._history) > self.max_size:
            self._history.pop(0)
        self._cursor = len(self._history)

    def previous(self) -> Optional[str]:
        if not self._history:
            return None
        if self._cursor > 0:
            self._cursor -= 1
            return self._history[self._cursor]
        return self._history[0]

    def next(self) -> Optional[str]:
        if not self._history:
            return None
        if self._cursor < len(self._history) - 1:
            self._cursor += 1
            return self._history[self._cursor]
        self._cursor = len(self._history)
        return ""
