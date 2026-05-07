"""Executor agent — translates decisions into ardi-agent CLI calls."""

from __future__ import annotations

from collections.abc import Iterable

from ..ardi import ArdiAgent
from ..config import Settings
from ..logging import get_logger
from ..models import (
    CommitDecision,
    CommitRecord,
    InscribeRecord,
    RevealRecord,
)

log = get_logger(__name__)


class ExecutorAgent:
    """Performs on-chain commits/reveals/inscribes via ArdiAgent."""

    def __init__(self, settings: Settings, ardi: ArdiAgent) -> None:
        self._settings = settings
        self._ardi = ardi

    # ---- Commit ------------------------------------------------------------

    def commit_all(self, decisions: Iterable[CommitDecision]) -> list[CommitRecord]:
        records: list[CommitRecord] = []
        for d in decisions:
            if not d.should_commit:
                log.debug("executor: skip word=%d (%s)", d.word_id, d.rationale)
                continue
            records.append(self._commit_one(d))
        return records

    def _commit_one(self, decision: CommitDecision) -> CommitRecord:
        if self._settings.dry_run:
            log.info(
                "executor[DRY]: commit epoch=%d word=%d answer=%r",
                decision.epoch,
                decision.word_id,
                decision.chosen_answer,
            )
            return CommitRecord(
                word_id=decision.word_id,
                epoch=decision.epoch,
                answer=decision.chosen_answer,
                tx_hash=None,
                status="confirmed",
                error=None,
            )

        log.info(
            "executor: committing word=%d answer=%r (conf=%.2f)",
            decision.word_id,
            decision.chosen_answer,
            decision.confidence,
        )
        record = self._ardi.commit(word_id=decision.word_id, answer=decision.chosen_answer)
        if record.status == "confirmed":
            log.info(
                "executor: commit OK word=%d tx=%s bond=%.4fETH",
                record.word_id,
                record.tx_hash,
                record.bond_eth,
            )
        else:
            log.error("executor: commit FAILED word=%d err=%s", record.word_id, record.error)
        # Make sure epoch is populated
        if record.epoch == 0:
            record.epoch = decision.epoch
        return record

    # ---- Reveal ------------------------------------------------------------

    def reveal_all(self, commits: Iterable[CommitRecord]) -> list[RevealRecord]:
        records: list[RevealRecord] = []
        for commit in commits:
            if commit.status != "confirmed":
                continue
            records.append(self._reveal_one(commit))
        return records

    def _reveal_one(self, commit: CommitRecord) -> RevealRecord:
        if self._settings.dry_run:
            log.info("executor[DRY]: reveal epoch=%d word=%d", commit.epoch, commit.word_id)
            return RevealRecord(
                word_id=commit.word_id,
                epoch=commit.epoch,
                revealed=True,
                tx_hash=None,
                won=None,
            )
        record = self._ardi.reveal(epoch=commit.epoch, word_id=commit.word_id)
        log.info(
            "executor: reveal epoch=%d word=%d revealed=%s won=%s tx=%s",
            record.epoch,
            record.word_id,
            record.revealed,
            record.won,
            record.tx_hash,
        )
        return record

    # ---- Inscribe ----------------------------------------------------------

    def inscribe_winners(self, reveals: Iterable[RevealRecord]) -> list[InscribeRecord]:
        records: list[InscribeRecord] = []
        for reveal in reveals:
            if not reveal.revealed or reveal.won is False:
                continue
            records.append(self._inscribe_one(reveal))
        return records

    def _inscribe_one(self, reveal: RevealRecord) -> InscribeRecord:
        if self._settings.dry_run:
            log.info("executor[DRY]: inscribe epoch=%d word=%d", reveal.epoch, reveal.word_id)
            return InscribeRecord(
                word_id=reveal.word_id,
                epoch=reveal.epoch,
                minted=True,
                token_id=None,
                tx_hash=None,
            )
        record = self._ardi.inscribe(epoch=reveal.epoch, word_id=reveal.word_id)
        if record.minted:
            log.info(
                "executor: MINTED token_id=%s tx=%s (epoch=%d word=%d)",
                record.token_id,
                record.tx_hash,
                record.epoch,
                record.word_id,
            )
        else:
            log.error("executor: inscribe failed word=%d err=%s", record.word_id, record.error)
        return record
