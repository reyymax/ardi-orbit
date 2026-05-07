"""Subprocess wrapper around the `ardi-agent` Rust CLI.

This module shells out to the binary published by awp-worknet/ardi-skill
and parses its plain-text / JSON output into typed records.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from .config import Settings
from .logging import get_logger
from .models import (
    CommitRecord,
    EpochState,
    InscribeRecord,
    Language,
    Preflight,
    RevealRecord,
    Riddle,
)

log = get_logger(__name__)


class ArdiAgentError(RuntimeError):
    """Raised when the underlying CLI fails or returns unparsable output."""


@dataclass(frozen=True)
class CliResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ArdiAgent:
    """Thin, testable wrapper around the `ardi-agent` binary."""

    def __init__(self, settings: Settings, *, runner=subprocess.run) -> None:
        self._settings = settings
        self._runner = runner  # injection point for tests

    # ---- low level ---------------------------------------------------------

    def _run(self, *args: str, timeout: float = 60.0) -> CliResult:
        cmd: tuple[str, ...] = (self._settings.ardi_agent_bin, *args)
        log.debug("$ %s", " ".join(shlex.quote(c) for c in cmd))
        try:
            proc = self._runner(
                list(cmd),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise ArdiAgentError(
                f"`{self._settings.ardi_agent_bin}` not found on PATH. "
                "Install via https://github.com/awp-worknet/ardi-skill or set ARDI_AGENT_BIN."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ArdiAgentError(f"ardi-agent timed out after {timeout}s: {' '.join(cmd)}") from exc

        result = CliResult(
            args=cmd,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
        if not result.ok:
            log.warning("ardi-agent %s exited %d: %s", args[0], result.returncode, result.stderr)
        return result

    # ---- high-level API ----------------------------------------------------

    def preflight(self) -> Preflight:
        result = self._run("preflight", timeout=30)
        return _parse_preflight(result.stdout + "\n" + result.stderr)

    def context(self) -> list[Riddle]:
        """Fetch the current epoch's 15 riddles."""
        # We always request JSON; if the binary doesn't support --json it falls
        # back to text and we still try to parse.
        result = self._run("context", "--json", timeout=30)
        if not result.ok and "--json" in result.stderr:
            # binary too old; retry without flag
            result = self._run("context", timeout=30)
        return _parse_context(result.stdout)

    def commit(self, *, word_id: int, answer: str) -> CommitRecord:
        result = self._run(
            "commit",
            "--word-id",
            str(word_id),
            "--answer",
            answer,
            timeout=120,
        )
        return _parse_commit(result, word_id=word_id, answer=answer)

    def reveal(self, *, epoch: int, word_id: int) -> RevealRecord:
        result = self._run(
            "reveal",
            "--epoch",
            str(epoch),
            "--word-id",
            str(word_id),
            timeout=120,
        )
        return _parse_reveal(result, epoch=epoch, word_id=word_id)

    def inscribe(self, *, epoch: int, word_id: int) -> InscribeRecord:
        result = self._run(
            "inscribe",
            "--epoch",
            str(epoch),
            "--word-id",
            str(word_id),
            timeout=180,
        )
        return _parse_inscribe(result, epoch=epoch, word_id=word_id)

    def commits_pending(self) -> Sequence[tuple[int, int]]:
        """Return list of (epoch, word_id) tuples that are revealable."""
        result = self._run("commits", "--json", timeout=20)
        if not result.ok and "--json" in result.stderr:
            result = self._run("commits", timeout=20)
        return _parse_pending(result.stdout)


# ---- parsers --------------------------------------------------------------

_TX_HASH_RE = re.compile(r"0x[a-fA-F0-9]{64}")
_GAS_RE = re.compile(r"(?:gas|balance)\s*[:=]\s*([0-9.]+)\s*ETH", re.IGNORECASE)
_TOKEN_ID_RE = re.compile(r"token[_\s-]?id\s*[:=]\s*(\d+)", re.IGNORECASE)


def _first_tx_hash(text: str) -> str | None:
    m = _TX_HASH_RE.search(text)
    return m.group(0) if m else None


def _parse_preflight(text: str) -> Preflight:
    lower = text.lower()
    gas_match = _GAS_RE.search(text)
    return Preflight(
        wallet_ok="wallet" in lower and "ok" in lower,
        registered="registered" in lower or "registration ok" in lower,
        coordinator_ok="coordinator" in lower and ("ok" in lower or "reachable" in lower),
        gas_eth=float(gas_match.group(1)) if gas_match else 0.0,
        stake_ok="stake" in lower and ("ok" in lower or "eligible" in lower),
        raw=text,
    )


def _parse_context(stdout: str) -> list[Riddle]:
    stdout = stdout.strip()
    if not stdout:
        return []
    # Preferred path: JSON
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return _parse_context_text(stdout)

    if isinstance(data, dict) and "riddles" in data:
        epoch = int(data.get("epoch", 0))
        items = data["riddles"]
    elif isinstance(data, list):
        items = data
        epoch = int(items[0].get("epoch", 0)) if items else 0
    else:
        raise ArdiAgentError(f"Unexpected context JSON shape: {data!r}")

    riddles: list[Riddle] = []
    for raw in items:
        riddles.append(
            Riddle(
                word_id=int(raw["word_id"]),
                epoch=int(raw.get("epoch", epoch)),
                prompt=str(raw.get("prompt") or raw.get("riddle") or "").strip(),
                language=_coerce_language(raw.get("language")),
                hint=raw.get("hint"),
                expected_length=raw.get("expected_length") or raw.get("length"),
            )
        )
    return riddles


def _parse_context_text(stdout: str) -> list[Riddle]:
    """Fallback text parser for older `ardi-agent context` output.

    Expected shape (best-effort):
        Epoch: 42
        [0] (en) What walks on four legs ...
        [1] (zh) 谜面 ...
    """
    epoch_match = re.search(r"epoch\s*[:#]?\s*(\d+)", stdout, re.IGNORECASE)
    epoch = int(epoch_match.group(1)) if epoch_match else 0
    riddles: list[Riddle] = []
    line_re = re.compile(r"^\s*\[?(\d+)\]?\s*(?:\(([a-z]{2})\))?\s*[:.\-]?\s*(.+)$")
    for line in stdout.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        word_id = int(m.group(1))
        lang = _coerce_language(m.group(2))
        prompt = m.group(3).strip()
        if not prompt or word_id > 99:  # ignore obviously bogus matches
            continue
        riddles.append(Riddle(word_id=word_id, epoch=epoch, prompt=prompt, language=lang))
    return riddles


def _coerce_language(value: object) -> Language:
    if not value:
        return Language.UNKNOWN
    try:
        return Language(str(value).lower())
    except ValueError:
        return Language.UNKNOWN


def _parse_commit(result: CliResult, *, word_id: int, answer: str) -> CommitRecord:
    record = CommitRecord(
        word_id=word_id,
        epoch=_extract_epoch(result.stdout) or 0,
        answer=answer,
        tx_hash=_first_tx_hash(result.stdout),
        status="confirmed" if result.ok else "failed",
        error=None if result.ok else (result.stderr.strip() or "commit failed"),
    )
    bond_match = re.search(r"bond\s*[:=]\s*([0-9.]+)\s*ETH", result.stdout, re.IGNORECASE)
    if bond_match:
        record.bond_eth = float(bond_match.group(1))
    return record


def _parse_reveal(result: CliResult, *, epoch: int, word_id: int) -> RevealRecord:
    won: bool | None = None
    lower = result.stdout.lower()
    if "won" in lower or "winner" in lower:
        won = True
    elif "lost" in lower or "no win" in lower:
        won = False
    return RevealRecord(
        word_id=word_id,
        epoch=epoch,
        revealed=result.ok,
        tx_hash=_first_tx_hash(result.stdout),
        won=won,
        error=None if result.ok else (result.stderr.strip() or "reveal failed"),
    )


def _parse_inscribe(result: CliResult, *, epoch: int, word_id: int) -> InscribeRecord:
    token_id_match = _TOKEN_ID_RE.search(result.stdout)
    return InscribeRecord(
        word_id=word_id,
        epoch=epoch,
        minted=result.ok,
        token_id=int(token_id_match.group(1)) if token_id_match else None,
        tx_hash=_first_tx_hash(result.stdout),
        error=None if result.ok else (result.stderr.strip() or "inscribe failed"),
    )


def _parse_pending(stdout: str) -> list[tuple[int, int]]:
    stdout = stdout.strip()
    if not stdout:
        return []
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return [(int(x["epoch"]), int(x["word_id"])) for x in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    pairs: list[tuple[int, int]] = []
    for line in stdout.splitlines():
        m = re.search(r"epoch\s*[:=]?\s*(\d+).*?word[_\s-]?id\s*[:=]?\s*(\d+)", line, re.IGNORECASE)
        if m:
            pairs.append((int(m.group(1)), int(m.group(2))))
    return pairs


def _extract_epoch(text: str) -> int | None:
    m = re.search(r"epoch\s*[:#]?\s*(\d+)", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def empty_state(epoch: int) -> EpochState:
    """Helper for tests / fresh runs."""
    return EpochState(epoch=epoch)
