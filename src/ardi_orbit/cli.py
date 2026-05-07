"""Typer-based CLI for ardi-orbit."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .agents.monitor import MonitorAgent, load_epoch_state
from .ardi import ArdiAgentError
from .config import load_settings
from .logging import banner, console, setup_logging

app = typer.Typer(
    add_completion=False,
    help="LLM-driven autonomous mining agent for the Ardi WorkNet.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def _bail(message: str, code: int = 1) -> typer.Exit:
    """Print a red error line and return an Exit suitable for `raise`."""
    console.print(f"[bold red]error:[/bold red] {message}")
    return typer.Exit(code=code)


@app.callback()
def _root(
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="DEBUG / INFO / WARNING / ERROR"),
    ] = "INFO",
) -> None:
    """Common options."""
    setup_logging(log_level)


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"ardi-orbit [bold]{__version__}[/bold]")


@app.command()
def preflight() -> None:
    """Run preflight checks via the underlying ardi-agent binary."""
    settings = load_settings()
    monitor = MonitorAgent(settings)
    try:
        pf = monitor.preflight()
    except ArdiAgentError as exc:
        raise _bail(str(exc)) from exc
    if not pf.ready:
        raise typer.Exit(code=1)


@app.command()
def run(
    once: Annotated[bool, typer.Option(help="Run a single epoch and exit.")] = True,
    skip_reveal: Annotated[bool, typer.Option(help="Stop after commit phase (no reveal/mint).")] = False,
    dry_run: Annotated[
        bool | None,
        typer.Option(help="Override ARDI_ORBIT_DRY_RUN. None = use env value."),
    ] = None,
) -> None:
    """Run the full mining loop for one (or more) epochs."""
    settings = load_settings()
    if dry_run is not None:
        settings.dry_run = dry_run
    if settings.dry_run:
        banner("DRY-RUN MODE — no on-chain transactions will be sent")

    monitor = MonitorAgent(settings)
    state = None
    try:
        while True:
            state = monitor.run_epoch(skip_reveal=skip_reveal)
            if once:
                break
            import time

            time.sleep(60)
    except ArdiAgentError as exc:
        raise _bail(str(exc)) from exc
    raise typer.Exit(code=0 if state and state.commits else 2)


@app.command()
def recover() -> None:
    """Resume any pending commits — reveal + inscribe wherever possible."""
    settings = load_settings()
    monitor = MonitorAgent(settings)
    try:
        monitor.recover_pending()
    except ArdiAgentError as exc:
        raise _bail(str(exc)) from exc


@app.command(name="show")
def show_state(
    epoch: Annotated[int, typer.Argument(help="Epoch number to inspect.")],
) -> None:
    """Pretty-print a persisted epoch state file."""
    settings = load_settings()
    path = settings.expanded_state_dir() / f"epoch-{epoch:06d}.json"
    if not path.exists():
        console.print(f"[red]no state file at {path}")
        raise typer.Exit(code=1)
    state = load_epoch_state(Path(path))
    console.print_json(state.model_dump_json())


if __name__ == "__main__":
    app()
