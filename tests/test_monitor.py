"""End-to-end test of MonitorAgent.run_epoch with all collaborators stubbed."""

from __future__ import annotations

import json
from pathlib import Path

from ardi_orbit.agents.monitor import MonitorAgent
from ardi_orbit.agents.solver import _SolverResponse
from ardi_orbit.agents.strategy import _StrategyResponse
from ardi_orbit.models import Language

from .conftest import FakeProc


def test_run_epoch_dry_persists_state(monkeypatch, settings, ardi_agent, tmp_path):
    settings.dry_run = True
    settings.state_dir = tmp_path  # type: ignore[assignment]

    # Solver always returns confident answers
    monkeypatch.setattr(
        "ardi_orbit.agents.solver.chat_json",
        lambda **_: _SolverResponse(answer="x", confidence=0.95, detected_language="en"),
    )
    # Strategy LLM does nothing (baseline carries us)
    monkeypatch.setattr(
        "ardi_orbit.agents.strategy.chat_json", lambda **_: _StrategyResponse(decisions=[])
    )

    riddles_payload = {
        "epoch": 100,
        "riddles": [
            {"word_id": i, "prompt": f"r{i}", "language": Language.EN.value} for i in range(3)
        ],
    }
    routes = {
        ("preflight",): FakeProc(
            stdout="wallet ok\nregistered ok\ncoordinator ok\ngas: 0.05 ETH\nstake ok"
        ),
        ("context", "--json"): FakeProc(stdout=json.dumps(riddles_payload)),
    }
    monitor = MonitorAgent(settings, ardi=ardi_agent(routes), sleep=lambda _s: None)
    state = monitor.run_epoch()

    assert state.epoch == 100
    assert len(state.riddles) == 3
    assert len(state.attempts) == 3
    assert sum(1 for d in state.decisions if d.should_commit) == settings.max_commits_per_epoch
    assert all(c.status == "confirmed" for c in state.commits)
    persisted = Path(settings.expanded_state_dir()) / f"epoch-{state.epoch:06d}.json"
    assert persisted.exists()
    on_disk = json.loads(persisted.read_text())
    assert on_disk["epoch"] == 100
