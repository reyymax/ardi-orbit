"""Monitor agent — orchestrates one full epoch of the mining loop."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from rich.table import Table

from ..ardi import ArdiAgent
from ..config import Settings
from ..logging import banner, console, get_logger
from ..models import EpochState, Preflight
from .executor import ExecutorAgent
from .solver import SolverAgent
from .strategy import StrategyAgent

log = get_logger(__name__)


# Default chain timing windows (seconds). These mirror the README guidance:
# "wait for commit window to close + ~30s" and "wait ~30s for VRF".
DEFAULT_REVEAL_WAIT_S = 35
DEFAULT_VRF_WAIT_S = 35


class MonitorAgent:
    """Top-level orchestrator. Runs solve → strategize → commit → reveal → inscribe."""

    def __init__(
        self,
        settings: Settings,
        *,
        ardi: ArdiAgent | None = None,
        solver: SolverAgent | None = None,
        strategy: StrategyAgent | None = None,
        executor: ExecutorAgent | None = None,
        sleep=time.sleep,
    ) -> None:
        self._settings = settings
        self._ardi = ardi or ArdiAgent(settings)
        self._solver = solver or SolverAgent(settings)
        self._strategy = strategy or StrategyAgent(settings)
        self._executor = executor or ExecutorAgent(settings, self._ardi)
        self._sleep = sleep

    # ---- Public entrypoints ------------------------------------------------

    def preflight(self) -> Preflight:
        banner("Preflight")
        pf = self._ardi.preflight()
        log.info(
            "preflight: wallet=%s registered=%s coordinator=%s gas=%.4fETH stake=%s ready=%s",
            pf.wallet_ok,
            pf.registered,
            pf.coordinator_ok,
            pf.gas_eth,
            pf.stake_ok,
            pf.ready,
        )
        return pf

    def run_epoch(
        self,
        *,
        skip_reveal: bool = False,
        reveal_wait_s: int = DEFAULT_REVEAL_WAIT_S,
        vrf_wait_s: int = DEFAULT_VRF_WAIT_S,
    ) -> EpochState:
        """Execute one full epoch of the mining loop."""
        pf = self.preflight()

        banner("Fetching riddles")
        riddles = self._ardi.context()
        if not riddles:
            log.warning("no riddles returned from ardi-agent context — exiting epoch")
            return EpochState(epoch=0, finished_at=datetime.utcnow())
        epoch = riddles[0].epoch
        log.info("fetched %d riddles for epoch=%d", len(riddles), epoch)

        state = EpochState(epoch=epoch, riddles=riddles)

        banner("Solving riddles")
        state.attempts = self._solver.solve_all(riddles)

        banner("Strategy")
        state.decisions = self._strategy.decide(
            riddles=riddles,
            attempts=state.attempts,
            preflight=pf,
        )
        self._render_strategy_table(state)

        banner("Commit phase")
        state.commits = self._executor.commit_all(state.decisions)
        if not state.commits:
            log.warning("no commits issued this epoch")
            state.finished_at = datetime.utcnow()
            self._persist(state)
            return state

        if skip_reveal:
            log.info("skip_reveal=True; stopping after commit phase")
            state.finished_at = datetime.utcnow()
            self._persist(state)
            return state

        banner(f"Waiting {reveal_wait_s}s for commit window + reveal phase")
        self._sleep(reveal_wait_s)

        state.reveals = self._executor.reveal_all(state.commits)

        banner(f"Waiting {vrf_wait_s}s for Chainlink VRF")
        self._sleep(vrf_wait_s)

        banner("Inscribe phase")
        state.inscribes = self._executor.inscribe_winners(state.reveals)

        state.finished_at = datetime.utcnow()
        self._persist(state)
        self._render_summary(state)
        return state

    # ---- Persistence -------------------------------------------------------

    def _persist(self, state: EpochState) -> Path:
        state_dir = self._settings.expanded_state_dir()
        path = state_dir / f"epoch-{state.epoch:06d}.json"
        path.write_text(state.model_dump_json(indent=2))
        log.info("persisted epoch state -> %s", path)
        return path

    # ---- Reporting ---------------------------------------------------------

    def _render_strategy_table(self, state: EpochState) -> None:
        table = Table(title=f"Strategy decisions (epoch {state.epoch})")
        table.add_column("word", justify="right")
        table.add_column("lang")
        table.add_column("answer")
        table.add_column("conf", justify="right")
        table.add_column("commit?", justify="center")
        table.add_column("rationale")

        riddles = {r.word_id: r for r in state.riddles}
        for d in state.decisions:
            r = riddles.get(d.word_id)
            table.add_row(
                str(d.word_id),
                r.language.value if r else "?",
                d.chosen_answer or "-",
                f"{d.confidence:.2f}",
                "[green]YES" if d.should_commit else "[dim]no",
                d.rationale,
            )
        console.print(table)

    def _render_summary(self, state: EpochState) -> None:
        committed = sum(1 for c in state.commits if c.status == "confirmed")
        revealed = sum(1 for r in state.reveals if r.revealed)
        won = sum(1 for r in state.reveals if r.won)
        minted = sum(1 for i in state.inscribes if i.minted)
        log.info(
            "epoch %d summary: committed=%d revealed=%d won=%d minted=%d",
            state.epoch,
            committed,
            revealed,
            won,
            minted,
        )

    # ---- Recovery ----------------------------------------------------------

    def recover_pending(self) -> EpochState:
        """Resume a partially-executed epoch by checking pending commits."""
        banner("Recovery")
        pending = self._ardi.commits_pending()
        if not pending:
            log.info("no pending commits to recover")
            return EpochState(epoch=0, finished_at=datetime.utcnow())

        # Group by epoch and just reveal/inscribe everything we can.
        log.info("recovering %d pending commit(s)", len(pending))
        # We reconstruct a minimal CommitRecord list from pending tuples.
        from ..models import CommitRecord  # local import to keep models lean above

        commits = [
            CommitRecord(epoch=e, word_id=w, answer="(unknown)", status="confirmed")
            for (e, w) in pending
        ]
        epoch = commits[0].epoch if commits else 0
        state = EpochState(epoch=epoch, commits=commits)
        state.reveals = self._executor.reveal_all(commits)
        self._sleep(DEFAULT_VRF_WAIT_S)
        state.inscribes = self._executor.inscribe_winners(state.reveals)
        state.finished_at = datetime.utcnow()
        self._persist(state)
        return state


def load_epoch_state(path: Path) -> EpochState:
    """Read a persisted epoch state file."""
    return EpochState.model_validate(json.loads(path.read_text()))
