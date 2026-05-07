"""Self-contained demo runner — no real chain, no real LLM, no binaries.

Exercises the full MonitorAgent.run_epoch() loop with:
 - A patched subprocess runner that pretends to be `ardi-agent`
 - Monkey-patched chat_json so solver + strategy use canned responses

Run:
    python demo/run_demo.py

Best results inside asciinema:
    asciinema rec demo.cast -c "python demo/run_demo.py"
"""

from __future__ import annotations

import random
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "demo"))

from demo_data import (  # noqa: E402
    DEMO_EPOCH,
    DEMO_RIDDLES,
    PREFLIGHT_STDOUT,
    build_context_json,
)

from ardi_orbit.agents.executor import ExecutorAgent  # noqa: E402
from ardi_orbit.agents.monitor import MonitorAgent  # noqa: E402
from ardi_orbit.agents.solver import _SolverResponse  # noqa: E402
from ardi_orbit.agents.strategy import _StrategyResponse  # noqa: E402
from ardi_orbit.ardi import ArdiAgent  # noqa: E402
from ardi_orbit.config import Settings  # noqa: E402
from ardi_orbit.logging import banner, console, setup_logging  # noqa: E402
from ardi_orbit.models import InscribeRecord, RevealRecord  # noqa: E402


# ---- Mock subprocess for `ardi-agent` --------------------------------------

def _fake_ardi_runner(cmd, check=False, capture_output=True, text=True, timeout=None):  # noqa: ARG001
    sub = cmd[1]  # ardi-agent <sub> ...
    if sub == "preflight":
        stdout = PREFLIGHT_STDOUT
    elif sub == "context":
        stdout = build_context_json()
    else:
        stdout = ""
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")


# ---- Mock LLM --------------------------------------------------------------

_RIDDLE_BY_ID = {r.word_id: r for r in DEMO_RIDDLES}


def _fake_chat_json(*, model, system, user, schema, settings, **kwargs):  # noqa: ARG001
    """Pretend to be chat_json: route by schema to either solver or strategy."""
    # Throttle so the demo reads as "the agent is thinking"
    time.sleep(random.uniform(0.25, 0.6))

    if schema is _SolverResponse:
        # Find which word_id we are solving for
        for line in user.splitlines():
            if line.startswith("word_id:"):
                word_id = int(line.split(":", 1)[1].strip())
                break
        else:
            word_id = 0
        r = _RIDDLE_BY_ID[word_id]
        return _SolverResponse(
            answer=r.mock_answer,
            confidence=r.mock_confidence,
            reasoning=r.mock_reasoning,
            alternates=list(r.mock_alternates),
            detected_language=r.language.value,
        )

    if schema is _StrategyResponse:
        # LLM strategy veto: pretend to flag riddle #11 (low-confidence Hindi one)
        # even though baseline already skips it — demonstrates the veto path.
        return _StrategyResponse(decisions=[])

    raise RuntimeError(f"unexpected schema in demo: {schema}")


# ---- Demo executor with simulated VRF outcomes ----------------------------


class _DemoExecutor(ExecutorAgent):
    """Simulates reveal wins and mint token IDs in dry-run mode.

    Winners are hard-coded so every recording tells the same story:
    the English 'map' riddle (word 0) and the 'keyboard' one (word 14)
    win the VRF lottery; the other three lose. ~40% win rate is
    representative of real Ardi worknet epochs.
    """

    _WINNER_WORD_IDS: frozenset[int] = frozenset({0, 14})

    def _reveal_one(self, commit):  # type: ignore[override]
        time.sleep(random.uniform(0.2, 0.45))
        rng = random.Random(commit.word_id * 7919 + 42)
        won = commit.word_id in self._WINNER_WORD_IDS
        tx = "0x" + f"{rng.randrange(16**64):064x}"
        from ardi_orbit.logging import get_logger

        result = "[green bold]WON[/green bold]" if won else "[dim]lost[/dim]"
        get_logger("demo").info(
            "executor: reveal  word=%-2d  %s  tx=%s…",
            commit.word_id,
            result,
            tx[:14],
        )
        return RevealRecord(
            word_id=commit.word_id,
            epoch=commit.epoch,
            revealed=True,
            tx_hash=tx,
            won=won,
        )

    def _inscribe_one(self, reveal):  # type: ignore[override]
        time.sleep(random.uniform(0.15, 0.4))
        rng = random.Random(reveal.word_id * 104729)
        token_id = 3000 + rng.randrange(100, 900)
        tx = "0x" + f"{rng.randrange(16**64):064x}"
        from ardi_orbit.logging import get_logger

        get_logger("demo").info(
            "executor: [bold green]MINTED[/bold green] token_id=#%d tx=%s… (word=%d)",
            token_id,
            tx[:14],
            reveal.word_id,
        )
        return InscribeRecord(
            word_id=reveal.word_id,
            epoch=reveal.epoch,
            minted=True,
            token_id=token_id,
            tx_hash=tx,
        )


# ---- Demo entrypoint -------------------------------------------------------

def main() -> int:
    setup_logging("INFO")

    banner("🌀  ardi-orbit demo  —  simulated epoch on Base mainnet")
    console.print(
        "[dim]LLM calls + ardi-agent subprocess are mocked with canned data "
        "so this runs offline for the recording.[/dim]"
    )
    console.print()

    # 1. Settings
    settings = Settings(
        ARDI_ORBIT_DRY_RUN=True,  # type: ignore[call-arg]
        ARDI_ORBIT_MIN_CONFIDENCE=0.70,  # type: ignore[call-arg]
        ARDI_ORBIT_MAX_COMMITS_PER_EPOCH=5,  # type: ignore[call-arg]
        ARDI_ORBIT_STATE_DIR=str(REPO_ROOT / ".demo-state"),  # type: ignore[call-arg]
        MIMO_API_KEY="sk-demo",  # type: ignore[call-arg]
        ARDI_ORBIT_SOLVER_MODEL="openai/mimo-v2.5-reasoner",  # type: ignore[call-arg]
        ARDI_ORBIT_STRATEGY_MODEL="openai/mimo-v2.5-flash",  # type: ignore[call-arg]
    )

    # 2. Patch the LLM layer
    import ardi_orbit.agents.solver as solver_mod
    import ardi_orbit.agents.strategy as strategy_mod

    solver_mod.chat_json = _fake_chat_json  # type: ignore[assignment]
    strategy_mod.chat_json = _fake_chat_json  # type: ignore[assignment]

    # 3. Wire up MonitorAgent with fake subprocess + simulated reveal outcomes
    ardi = ArdiAgent(settings, runner=_fake_ardi_runner)
    executor = _DemoExecutor(settings, ardi)
    monitor = MonitorAgent(
        settings,
        ardi=ardi,
        executor=executor,
        sleep=lambda s: time.sleep(min(s, 1.0)),
    )

    # 4. Run one epoch
    state = monitor.run_epoch()

    # 5. Final console summary
    console.print()
    banner("Epoch complete")
    committed = sum(1 for d in state.decisions if d.should_commit)
    skipped = sum(1 for d in state.decisions if not d.should_commit)
    won = sum(1 for r in state.reveals if r.won)
    minted = sum(1 for i in state.inscribes if i.minted)
    console.print(
        f"[bold]epoch {state.epoch}[/bold]  ·  "
        f"riddles: {len(state.riddles)}  ·  "
        f"solved: {len(state.attempts)}  ·  "
        f"[green]commits: {committed}[/green]  ·  "
        f"[dim]skipped: {skipped}[/dim]  ·  "
        f"[yellow]won: {won}[/yellow]  ·  "
        f"[magenta bold]minted: {minted}[/magenta bold]"
    )
    if state.inscribes:
        console.print()
        console.print("[bold]Minted Ardinals this epoch:[/bold]")
        for i in state.inscribes:
            if i.minted:
                console.print(
                    f"  · token #{i.token_id}  "
                    f"[dim](epoch {i.epoch}, word {i.word_id})[/dim]"
                )
    console.print(
        "\n[dim]state persisted →[/dim] "
        f"{settings.expanded_state_dir() / f'epoch-{DEMO_EPOCH:06d}.json'}"
    )
    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
