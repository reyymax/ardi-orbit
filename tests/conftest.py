"""Shared pytest fixtures."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from ardi_orbit.ardi import ArdiAgent
from ardi_orbit.config import Settings


@dataclass
class FakeProc:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ARDI_ORBIT_STATE_DIR=str(tmp_path / "state"),  # type: ignore[call-arg]
        ARDI_ORBIT_DRY_RUN=True,  # type: ignore[call-arg]
        ARDI_ORBIT_MIN_CONFIDENCE=0.7,  # type: ignore[call-arg]
        ARDI_ORBIT_MAX_COMMITS_PER_EPOCH=3,  # type: ignore[call-arg]
        MIMO_API_KEY="sk-test",  # type: ignore[call-arg]
    )


@pytest.fixture
def make_runner() -> Callable[[dict[tuple[str, ...], FakeProc]], Callable]:
    """Build a subprocess.run-compatible callable from a route table.

    Routes are matched by the suffix of args after the binary path.
    """

    def _build(routes: dict[tuple[str, ...], FakeProc]):
        def runner(cmd, check=False, capture_output=True, text=True, timeout=None):
            key = tuple(cmd[1:])  # drop binary
            for route_key, proc in routes.items():
                if key[: len(route_key)] == route_key:
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
                    )
            raise AssertionError(f"unrouted ardi-agent call: {key}")

        return runner

    return _build


@pytest.fixture
def ardi_agent(settings, make_runner):
    """ArdiAgent that defaults to FileNotFoundError unless routes are provided."""

    def _factory(routes: dict[tuple[str, ...], FakeProc]) -> ArdiAgent:
        return ArdiAgent(settings, runner=make_runner(routes))

    return _factory
