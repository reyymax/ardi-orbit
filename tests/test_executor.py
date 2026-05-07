"""Tests for ExecutorAgent — exercises both dry-run and live paths via FakeProc."""

from __future__ import annotations

from ardi_orbit.agents.executor import ExecutorAgent
from ardi_orbit.models import CommitDecision, CommitRecord, RevealRecord

from .conftest import FakeProc


def _yes(word_id: int, answer: str = "x", conf: float = 0.9) -> CommitDecision:
    return CommitDecision(
        word_id=word_id,
        epoch=1,
        should_commit=True,
        chosen_answer=answer,
        confidence=conf,
        rationale="top pick",
    )


def _no(word_id: int) -> CommitDecision:
    return CommitDecision(
        word_id=word_id,
        epoch=1,
        should_commit=False,
        chosen_answer="x",
        confidence=0.1,
        rationale="too low",
    )


def test_dry_run_skips_real_calls(settings, ardi_agent):
    settings.dry_run = True
    ardi = ardi_agent({})  # any call would fail
    executor = ExecutorAgent(settings, ardi)
    records = executor.commit_all([_yes(0), _no(1), _yes(2)])
    assert len(records) == 2
    assert all(r.status == "confirmed" and r.tx_hash is None for r in records)


def test_live_commit_invokes_ardi_agent(settings, ardi_agent):
    settings.dry_run = False
    tx = "0x" + "ab" * 32
    routes = {
        ("commit", "--word-id", "0", "--answer", "x"): FakeProc(
            stdout=f"epoch: 1\nbond: 0.005 ETH\ntx: {tx}\nOK"
        ),
    }
    executor = ExecutorAgent(settings, ardi_agent(routes))
    records = executor.commit_all([_yes(0)])
    assert len(records) == 1
    assert records[0].status == "confirmed"
    assert records[0].tx_hash == tx


def test_reveal_only_runs_for_confirmed(settings, ardi_agent):
    settings.dry_run = False
    tx = "0x" + "cd" * 32
    routes = {
        ("reveal", "--epoch", "1", "--word-id", "0"): FakeProc(stdout=f"won! tx: {tx}"),
    }
    executor = ExecutorAgent(settings, ardi_agent(routes))
    commits = [
        CommitRecord(word_id=0, epoch=1, answer="x", status="confirmed", tx_hash="0x" + "11" * 32),
        CommitRecord(word_id=1, epoch=1, answer="y", status="failed", error="nope"),
    ]
    reveals = executor.reveal_all(commits)
    assert len(reveals) == 1
    assert reveals[0].won is True


def test_inscribe_only_runs_for_winners(settings, ardi_agent):
    settings.dry_run = False
    tx = "0x" + "ef" * 32
    routes = {
        ("inscribe", "--epoch", "1", "--word-id", "0"): FakeProc(
            stdout=f"minted token_id: 7 tx={tx}"
        ),
    }
    executor = ExecutorAgent(settings, ardi_agent(routes))
    reveals = [
        RevealRecord(word_id=0, epoch=1, revealed=True, won=True, tx_hash="0x" + "aa" * 32),
        RevealRecord(word_id=1, epoch=1, revealed=True, won=False, tx_hash="0x" + "bb" * 32),
        RevealRecord(word_id=2, epoch=1, revealed=False, won=None),
    ]
    inscribes = executor.inscribe_winners(reveals)
    assert len(inscribes) == 1
    assert inscribes[0].minted
    assert inscribes[0].token_id == 7
