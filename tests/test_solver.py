"""Tests for the SolverAgent (LLM mocked)."""

from __future__ import annotations

import pytest

from ardi_orbit.agents.solver import SolverAgent, _SolverResponse
from ardi_orbit.llm import LLMError
from ardi_orbit.models import Language, Riddle


@pytest.fixture
def riddle() -> Riddle:
    return Riddle(
        word_id=0,
        epoch=42,
        prompt="What has roots that nobody sees, is taller than trees?",
        language=Language.EN,
    )


def test_solver_returns_normalized_answer(monkeypatch, settings, riddle):
    def fake_chat_json(**kwargs):
        return _SolverResponse(
            answer="  Mountain ",
            confidence=0.92,
            reasoning="Tolkien Hobbit riddle.",
            alternates=["Tree"],
            detected_language="en",
        )

    monkeypatch.setattr("ardi_orbit.agents.solver.chat_json", fake_chat_json)
    attempt = SolverAgent(settings).solve(riddle)
    assert attempt.answer == "mountain"
    assert attempt.alternates == ["tree"]
    assert attempt.confidence == pytest.approx(0.92)
    assert attempt.model == settings.solver_model
    assert attempt.epoch == 42


def test_solver_handles_llm_error(monkeypatch, settings, riddle):
    def boom(**kwargs):
        raise LLMError("boom")

    monkeypatch.setattr("ardi_orbit.agents.solver.chat_json", boom)
    attempt = SolverAgent(settings).solve(riddle)
    assert attempt.answer == ""
    assert attempt.confidence == 0.0
    assert "boom" in attempt.reasoning


def test_solver_solve_all(monkeypatch, settings):
    riddles = [
        Riddle(word_id=i, epoch=1, prompt=f"riddle {i}", language=Language.EN) for i in range(3)
    ]

    def fake(**kwargs):
        return _SolverResponse(answer="x", confidence=0.5, detected_language="en")

    monkeypatch.setattr("ardi_orbit.agents.solver.chat_json", fake)
    attempts = SolverAgent(settings).solve_all(riddles)
    assert len(attempts) == 3
    assert {a.word_id for a in attempts} == {0, 1, 2}
