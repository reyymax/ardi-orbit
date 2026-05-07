"""Strategy agent — decides which solved riddles are worth committing on chain."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import Settings
from ..llm import LLMError, chat_json
from ..logging import get_logger
from ..models import CommitDecision, Preflight, Riddle, SolveAttempt

log = get_logger(__name__)


STRATEGY_SYSTEM_PROMPT = """\
You are the Strategy agent for the Ardi WorkNet mining loop. Each commit \
locks a small ETH bond on Base mainnet that is forfeit if the answer is \
wrong on reveal. You must rank candidate solve attempts and return the top \
N to commit, given the operator's gas budget.

Inputs you receive:
- A ranked list of (riddle, attempt) pairs
- The operator's available gas in ETH
- Maximum commits allowed this epoch
- Minimum confidence threshold

Rules:
- Never recommend committing if confidence < the configured threshold.
- Prefer diversity in language when scores tie (network values multilingual).
- Output STRICT JSON. No commentary outside JSON.
"""


class _StrategyDecision(BaseModel):
    word_id: int
    should_commit: bool
    rationale: str = Field(default="", max_length=400)


class _StrategyResponse(BaseModel):
    decisions: list[_StrategyDecision]


class StrategyAgent:
    """LLM-assisted commit selector with deterministic fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def decide(
        self,
        *,
        riddles: list[Riddle],
        attempts: list[SolveAttempt],
        preflight: Preflight,
        estimated_commit_cost_eth: float = 0.005,
    ) -> list[CommitDecision]:
        if not attempts:
            return []

        # ---- Deterministic baseline ---------------------------------------
        # We always compute this; the LLM may only refine ordering / vetoes.
        baseline = self._baseline(
            riddles=riddles,
            attempts=attempts,
            preflight=preflight,
            estimated_commit_cost_eth=estimated_commit_cost_eth,
        )

        # ---- LLM refinement (optional, soft-fail) -------------------------
        try:
            llm_overrides = self._ask_llm(riddles=riddles, attempts=attempts, preflight=preflight)
        except LLMError as exc:
            log.warning("strategy: LLM refinement failed (%s); using baseline only", exc)
            llm_overrides = {}

        # Apply: LLM can VETO a commit but cannot promote a low-confidence one.
        for decision in baseline:
            override = llm_overrides.get(decision.word_id)
            if override is None:
                continue
            if override.should_commit is False and decision.should_commit:
                decision.should_commit = False
                decision.rationale = f"LLM veto: {override.rationale}"
        return baseline

    # ---- internals ---------------------------------------------------------

    def _baseline(
        self,
        *,
        riddles: list[Riddle],
        attempts: list[SolveAttempt],
        preflight: Preflight,
        estimated_commit_cost_eth: float,
    ) -> list[CommitDecision]:
        riddle_by_id = {r.word_id: r for r in riddles}
        # Sort attempts by confidence descending
        ranked = sorted(attempts, key=lambda a: a.confidence, reverse=True)

        max_by_gas = (
            int(preflight.gas_eth // estimated_commit_cost_eth)
            if estimated_commit_cost_eth > 0
            else self._settings.max_commits_per_epoch
        )
        budget = max(0, min(self._settings.max_commits_per_epoch, max_by_gas))

        decisions: list[CommitDecision] = []
        committed = 0
        for att in ranked:
            riddle = riddle_by_id.get(att.word_id)
            if riddle is None:
                continue

            if not att.answer:
                decisions.append(
                    CommitDecision(
                        word_id=att.word_id,
                        epoch=att.epoch,
                        should_commit=False,
                        chosen_answer="",
                        confidence=att.confidence,
                        rationale="empty answer",
                        estimated_gas_eth=estimated_commit_cost_eth,
                    )
                )
                continue

            ok = (
                att.confidence >= self._settings.min_confidence
                and committed < budget
                and preflight.ready
            )
            rationale_parts = []
            if att.confidence < self._settings.min_confidence:
                rationale_parts.append(
                    f"confidence {att.confidence:.2f} < threshold {self._settings.min_confidence}"
                )
            if committed >= budget:
                rationale_parts.append(f"epoch budget {budget} exhausted")
            if not preflight.ready:
                rationale_parts.append("preflight not ready")
            if ok:
                rationale_parts.append(
                    f"top-{committed + 1} pick, conf={att.confidence:.2f}, lang={riddle.language.value}"
                )

            decisions.append(
                CommitDecision(
                    word_id=att.word_id,
                    epoch=att.epoch,
                    should_commit=ok,
                    chosen_answer=att.answer,
                    confidence=att.confidence,
                    rationale="; ".join(rationale_parts),
                    estimated_gas_eth=estimated_commit_cost_eth,
                )
            )
            if ok:
                committed += 1

        return decisions

    def _ask_llm(
        self,
        *,
        riddles: list[Riddle],
        attempts: list[SolveAttempt],
        preflight: Preflight,
    ) -> dict[int, _StrategyDecision]:
        riddle_by_id = {r.word_id: r for r in riddles}
        lines = [
            f"gas_eth: {preflight.gas_eth}",
            f"min_confidence: {self._settings.min_confidence}",
            f"max_commits_per_epoch: {self._settings.max_commits_per_epoch}",
            "",
            "Candidates (word_id, language, confidence, answer, prompt):",
        ]
        for att in attempts:
            r = riddle_by_id.get(att.word_id)
            if r is None:
                continue
            lines.append(
                f"- {att.word_id} | {r.language.value} | {att.confidence:.2f} "
                f"| {att.answer!r} | {r.prompt[:160]}"
            )
        lines.append("")
        lines.append('Respond with JSON: {"decisions": [{"word_id": N, "should_commit": bool, "rationale": "..."}]}')

        resp = chat_json(
            model=self._settings.strategy_model,
            system=STRATEGY_SYSTEM_PROMPT,
            user="\n".join(lines),
            schema=_StrategyResponse,
            settings=self._settings,
            temperature=0.0,
            max_tokens=1024,
        )
        return {d.word_id: d for d in resp.decisions}
