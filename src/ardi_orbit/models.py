"""Pydantic data models for riddles, decisions, and on-chain state."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Language(StrEnum):
    """Languages observed in Ardi riddle corpus (ISO 639-1)."""

    EN = "en"
    ZH = "zh"
    ID = "id"
    JA = "ja"
    KO = "ko"
    AR = "ar"
    ES = "es"
    FR = "fr"
    DE = "de"
    RU = "ru"
    PT = "pt"
    HI = "hi"
    UNKNOWN = "unknown"


class Riddle(BaseModel):
    """A single multilingual riddle from `ardi-agent context`."""

    word_id: int = Field(..., ge=0, description="Riddle index in the current epoch.")
    epoch: int = Field(..., ge=0)
    prompt: str = Field(..., min_length=1)
    language: Language = Field(default=Language.UNKNOWN)
    hint: str | None = None
    expected_length: int | None = Field(default=None, ge=1, le=64)


class SolveAttempt(BaseModel):
    """A solver agent's reasoned answer to a riddle."""

    word_id: int
    epoch: int
    answer: str = Field(default="", description="Empty string indicates a solver failure.")
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str = Field(default="", description="Chain-of-thought trace.")
    alternates: list[str] = Field(default_factory=list)
    model: str = ""
    solved_at: datetime = Field(default_factory=datetime.utcnow)


class CommitDecision(BaseModel):
    """Strategy agent's verdict on whether to commit on-chain."""

    word_id: int
    epoch: int
    should_commit: bool
    chosen_answer: str
    confidence: float
    rationale: str = ""
    estimated_gas_eth: float = Field(default=0.0, ge=0)


class CommitRecord(BaseModel):
    """Result of `ardi-agent commit`."""

    word_id: int
    epoch: int
    answer: str
    tx_hash: str | None = None
    bond_eth: float = 0.0
    committed_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["pending", "confirmed", "failed"] = "pending"
    error: str | None = None


class RevealRecord(BaseModel):
    """Result of `ardi-agent reveal`."""

    word_id: int
    epoch: int
    revealed: bool
    tx_hash: str | None = None
    won: bool | None = None
    error: str | None = None


class InscribeRecord(BaseModel):
    """Result of `ardi-agent inscribe` (NFT mint)."""

    word_id: int
    epoch: int
    minted: bool
    token_id: int | None = None
    tx_hash: str | None = None
    error: str | None = None


class EpochState(BaseModel):
    """Full record for a single epoch — used as the persistent state file."""

    epoch: int
    riddles: list[Riddle] = Field(default_factory=list)
    attempts: list[SolveAttempt] = Field(default_factory=list)
    decisions: list[CommitDecision] = Field(default_factory=list)
    commits: list[CommitRecord] = Field(default_factory=list)
    reveals: list[RevealRecord] = Field(default_factory=list)
    inscribes: list[InscribeRecord] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class Preflight(BaseModel):
    """Output of `ardi-agent preflight` parsed into structured form."""

    wallet_ok: bool = False
    registered: bool = False
    coordinator_ok: bool = False
    gas_eth: float = 0.0
    stake_ok: bool = False
    raw: str = ""

    @property
    def ready(self) -> bool:
        return all(
            [self.wallet_ok, self.registered, self.coordinator_ok, self.stake_ok, self.gas_eth > 0]
        )
