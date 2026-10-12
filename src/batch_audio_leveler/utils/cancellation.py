"""Graceful cancellation handling for long-running batch operations."""

from __future__ import annotations

import signal
import subprocess
from typing import Optional


class CancellationToken:
    """Thread-safe and signal-friendly cancellation tracker."""

    def __init__(self) -> None:
        self._cancelled: bool = False
        self._active_process: Optional[subprocess.Popen] = None
        self._old_sigint = None

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True
        if self._active_process and self._active_process.poll() is None:
            try:
                self._active_process.terminate()
            except Exception:
                pass

    def register_process(self, process: subprocess.Popen) -> None:
        self._active_process = process
        if self._cancelled and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    def unregister_process(self) -> None:
        self._active_process = None

    def __enter__(self) -> "CancellationToken":
        self._old_sigint = signal.getsignal(signal.SIGINT)

        def _handler(signum, frame):
            self.cancel()

        signal.signal(signal.SIGINT, _handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._old_sigint is not None:
            signal.signal(signal.SIGINT, self._old_sigint)
