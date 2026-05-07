"""Solver agent — turns a multilingual Riddle into a SolveAttempt via LLM reasoning."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import Settings
from ..llm import LLMError, chat_json
from ..logging import get_logger
from ..models import Riddle, SolveAttempt

log = get_logger(__name__)


SOLVER_SYSTEM_PROMPT = """\
You are the Solver agent for the Ardi WorkNet — a network where AI agents \
solve multilingual riddles to mint Ardinal NFTs on Base mainnet.

Your single task: given a riddle, return the SHORTEST canonical answer \
(usually a single word or short phrase, lowercased, no punctuation), with \
calibrated confidence and a brief reasoning trace.

Rules:
- Detect the language of the riddle and reason in it; output the answer in \
  the same language unless the riddle explicitly asks for another.
- Prefer literal nouns over abstract concepts when ambiguous.
- If the riddle has a known canonical answer in its source culture, use that.
- Output STRICT JSON matching the schema. No prose outside JSON.
- `confidence` must reflect calibrated probability that the answer is the \
  exact one the riddle protocol expects: 0.95 = near certain, 0.5 = coin flip.
- `alternates` should list 0-3 plausible alternatives in descending probability.
"""


class _SolverResponse(BaseModel):
    """Schema we ask the LLM to fill."""

    answer: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str = Field(default="", max_length=2000)
    alternates: list[str] = Field(default_factory=list, max_length=3)
    detected_language: str = Field(default="unknown")


class SolverAgent:
    """LLM-driven multilingual riddle solver."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def solve(self, riddle: Riddle) -> SolveAttempt:
        user_prompt = self._format_user_prompt(riddle)
        try:
            resp = chat_json(
                model=self._settings.solver_model,
                system=SOLVER_SYSTEM_PROMPT,
                user=user_prompt,
                schema=_SolverResponse,
                settings=self._settings,
                temperature=0.2,
                max_tokens=1024,
            )
        except LLMError as exc:
            log.error("solver: LLM failed for word_id=%d: %s", riddle.word_id, exc)
            return SolveAttempt(
                word_id=riddle.word_id,
                epoch=riddle.epoch,
                answer="",
                confidence=0.0,
                reasoning=f"LLM error: {exc}",
                model=self._settings.solver_model,
            )

        answer = _normalize_answer(resp.answer)
        log.info(
            "solver: epoch=%d word=%d lang=%s answer=%r conf=%.2f",
            riddle.epoch,
            riddle.word_id,
            resp.detected_language,
            answer,
            resp.confidence,
        )
        return SolveAttempt(
            word_id=riddle.word_id,
            epoch=riddle.epoch,
            answer=answer,
            confidence=resp.confidence,
            reasoning=resp.reasoning,
            alternates=[_normalize_answer(a) for a in resp.alternates if a],
            model=self._settings.solver_model,
        )

    def solve_all(self, riddles: list[Riddle]) -> list[SolveAttempt]:
        return [self.solve(r) for r in riddles]

    @staticmethod
    def _format_user_prompt(riddle: Riddle) -> str:
        parts = [
            f"epoch: {riddle.epoch}",
            f"word_id: {riddle.word_id}",
            f"declared_language: {riddle.language.value}",
        ]
        if riddle.expected_length:
            parts.append(f"expected_answer_length: {riddle.expected_length}")
        if riddle.hint:
            parts.append(f"hint: {riddle.hint}")
        parts.append("")
        parts.append("Riddle:")
        parts.append(riddle.prompt)
        parts.append("")
        parts.append(
            'Respond with JSON: {"answer": "...", "confidence": 0.0-1.0, '
            '"reasoning": "...", "alternates": ["..."], "detected_language": "xx"}'
        )
        return "\n".join(parts)


def _normalize_answer(raw: str) -> str:
    """Match the on-chain canonical form: trimmed, lowercased."""
    return raw.strip().lower()
