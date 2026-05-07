"""Tests for the StrategyAgent baseline + LLM veto behavior."""

from __future__ import annotations

import pytest

from ardi_orbit.agents.strategy import StrategyAgent, _StrategyDecision, _StrategyResponse
from ardi_orbit.llm import LLMError
from ardi_orbit.models import Language, Preflight, Riddle, SolveAttempt


@pytest.fixture
def ready_preflight() -> Preflight:
    return Preflight(
        wallet_ok=True,
        registered=True,
        coordinator_ok=True,
        gas_eth=0.05,
        stake_ok=True,
        raw="ok",
    )


def _riddles(n: int) -> list[Riddle]:
    langs = [Language.EN, Language.ZH, Language.ID, Language.JA, Language.KO]
    return [
        Riddle(
            word_id=i,
            epoch=1,
            prompt=f"riddle {i}",
            language=langs[i % len(langs)],
        )
        for i in range(n)
    ]


def _attempts(confidences: list[float]) -> list[SolveAttempt]:
    return [
        SolveAttempt(word_id=i, epoch=1, answer=f"ans{i}", confidence=c)
        for i, c in enumerate(confidences)
    ]


def test_strategy_skips_low_confidence(monkeypatch, settings, ready_preflight):
    monkeypatch.setattr(
        "ardi_orbit.agents.strategy.chat_json", lambda **_: _StrategyResponse(decisions=[])
    )
    riddles = _riddles(3)
    attempts = _attempts([0.9, 0.5, 0.3])  # threshold = 0.7

    decisions = StrategyAgent(settings).decide(
        riddles=riddles, attempts=attempts, preflight=ready_preflight
    )
    by_id = {d.word_id: d for d in decisions}
    assert by_id[0].should_commit
    assert not by_id[1].should_commit
    assert not by_id[2].should_commit


def test_strategy_respects_max_commits_per_epoch(monkeypatch, settings, ready_preflight):
    monkeypatch.setattr(
        "ardi_orbit.agents.strategy.chat_json", lambda **_: _StrategyResponse(decisions=[])
    )
    settings.max_commits_per_epoch = 2
    riddles = _riddles(5)
    attempts = _attempts([0.99, 0.98, 0.97, 0.96, 0.95])

    decisions = StrategyAgent(settings).decide(
        riddles=riddles, attempts=attempts, preflight=ready_preflight
    )
    yes = [d for d in decisions if d.should_commit]
    assert len(yes) == 2
    # Top two by confidence
    assert {d.word_id for d in yes} == {0, 1}


def test_strategy_gas_budget_caps_commits(monkeypatch, settings, ready_preflight):
    monkeypatch.setattr(
        "ardi_orbit.agents.strategy.chat_json", lambda **_: _StrategyResponse(decisions=[])
    )
    ready_preflight.gas_eth = 0.012  # only ~2 commits at 0.005 estimate
    riddles = _riddles(5)
    attempts = _attempts([0.95, 0.94, 0.93, 0.92, 0.91])

    decisions = StrategyAgent(settings).decide(
        riddles=riddles, attempts=attempts, preflight=ready_preflight
    )
    yes = [d for d in decisions if d.should_commit]
    assert len(yes) == 2


def test_strategy_skips_when_preflight_unready(monkeypatch, settings):
    monkeypatch.setattr(
        "ardi_orbit.agents.strategy.chat_json", lambda **_: _StrategyResponse(decisions=[])
    )
    pf = Preflight()  # all defaults => not ready
    decisions = StrategyAgent(settings).decide(
        riddles=_riddles(2),
        attempts=_attempts([0.99, 0.99]),
        preflight=pf,
    )
    assert all(not d.should_commit for d in decisions)


def test_strategy_llm_veto_overrides_yes(monkeypatch, settings, ready_preflight):
    def fake_chat(**kwargs):
        return _StrategyResponse(
            decisions=[_StrategyDecision(word_id=0, should_commit=False, rationale="ambiguous")]
        )

    monkeypatch.setattr("ardi_orbit.agents.strategy.chat_json", fake_chat)
    decisions = StrategyAgent(settings).decide(
        riddles=_riddles(2),
        attempts=_attempts([0.99, 0.99]),
        preflight=ready_preflight,
    )
    by_id = {d.word_id: d for d in decisions}
    assert not by_id[0].should_commit
    assert "LLM veto" in by_id[0].rationale
    assert by_id[1].should_commit  # untouched


def test_strategy_llm_cannot_promote_low_confidence(monkeypatch, settings, ready_preflight):
    def fake_chat(**kwargs):
        return _StrategyResponse(
            decisions=[_StrategyDecision(word_id=0, should_commit=True, rationale="trust me")]
        )

    monkeypatch.setattr("ardi_orbit.agents.strategy.chat_json", fake_chat)
    decisions = StrategyAgent(settings).decide(
        riddles=_riddles(1),
        attempts=_attempts([0.30]),
        preflight=ready_preflight,
    )
    assert decisions[0].should_commit is False  # baseline wins


def test_strategy_falls_back_when_llm_errors(monkeypatch, settings, ready_preflight):
    def boom(**kwargs):
        raise LLMError("nope")

    monkeypatch.setattr("ardi_orbit.agents.strategy.chat_json", boom)
    decisions = StrategyAgent(settings).decide(
        riddles=_riddles(1),
        attempts=_attempts([0.95]),
        preflight=ready_preflight,
    )
    assert decisions[0].should_commit  # baseline still works
