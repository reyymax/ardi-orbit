"""Rich-based structured logging."""

from __future__ import annotations

import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

console = Console()
_configured = False


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with Rich (idempotent)."""
    global _configured
    if _configured:
        return

    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        markup=True,
    )
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )
    # Quiet down noisy deps
    for noisy in ("httpx", "httpcore", "litellm", "LiteLLM"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger."""
    return logging.getLogger(name)


def banner(message: str, **kwargs: Any) -> None:
    """Print a highlighted banner line."""
    console.rule(f"[bold cyan]{message}", **kwargs)
