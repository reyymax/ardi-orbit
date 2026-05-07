"""Tests for the ardi-agent CLI wrapper."""

from __future__ import annotations

import json

from ardi_orbit.models import Language

from .conftest import FakeProc


def test_preflight_parses_ready(ardi_agent):
    routes = {
        ("preflight",): FakeProc(
            stdout=(
                "wallet: ok\n"
                "registered: ok\n"
                "coordinator: reachable\n"
                "gas: 0.05 ETH\n"
                "stake: ok\n"
            )
        ),
    }
    pf = ardi_agent(routes).preflight()
    assert pf.wallet_ok
    assert pf.registered
    assert pf.coordinator_ok
    assert pf.stake_ok
    assert pf.gas_eth == 0.05
    assert pf.ready


def test_preflight_unready_when_no_gas(ardi_agent):
    routes = {("preflight",): FakeProc(stdout="wallet ok\nstake ok\nregistered\ncoordinator ok\n")}
    pf = ardi_agent(routes).preflight()
    assert not pf.ready


def test_context_parses_json(ardi_agent):
    payload = {
        "epoch": 42,
        "riddles": [
            {"word_id": 0, "prompt": "What walks on four legs?", "language": "en"},
            {"word_id": 1, "prompt": "谜面：白日依山尽", "language": "zh"},  # noqa: RUF001
            {"word_id": 2, "prompt": "Apa yang hijau di kebun?", "language": "id"},
        ],
    }
    routes = {("context", "--json"): FakeProc(stdout=json.dumps(payload))}
    riddles = ardi_agent(routes).context()
    assert len(riddles) == 3
    assert riddles[0].epoch == 42
    assert riddles[1].language is Language.ZH
    assert riddles[2].language is Language.ID


def test_context_falls_back_to_text(ardi_agent):
    routes = {
        ("context", "--json"): FakeProc(returncode=2, stderr="unknown flag --json"),
        ("context",): FakeProc(
            stdout=(
                "Epoch: 7\n"
                "[0] (en) What walks on four legs at dawn?\n"
                "[1] (zh) 一个谜语\n"
                "[2] What flies without wings?\n"
            )
        ),
    }
    riddles = ardi_agent(routes).context()
    assert {r.word_id for r in riddles} == {0, 1, 2}
    assert all(r.epoch == 7 for r in riddles)


def test_commit_parses_tx_hash(ardi_agent):
    tx = "0x" + "ab" * 32
    routes = {
        ("commit", "--word-id", "3", "--answer", "elephant"): FakeProc(
            stdout=f"epoch: 11\nbond: 0.0050 ETH\ntx: {tx}\nOK\n"
        ),
    }
    rec = ardi_agent(routes).commit(word_id=3, answer="elephant")
    assert rec.status == "confirmed"
    assert rec.tx_hash == tx
    assert rec.epoch == 11
    assert rec.bond_eth == 0.005


def test_commit_failure_captured(ardi_agent):
    routes = {
        ("commit", "--word-id", "0", "--answer", "wrong"): FakeProc(
            returncode=1, stderr="commit window closed"
        ),
    }
    rec = ardi_agent(routes).commit(word_id=0, answer="wrong")
    assert rec.status == "failed"
    assert rec.error == "commit window closed"
    assert rec.tx_hash is None


def test_reveal_detects_win(ardi_agent):
    tx = "0x" + "cd" * 32
    routes = {
        ("reveal", "--epoch", "9", "--word-id", "4"): FakeProc(
            stdout=f"revealed; you WON the lottery\ntx: {tx}\n"
        ),
    }
    rec = ardi_agent(routes).reveal(epoch=9, word_id=4)
    assert rec.revealed
    assert rec.won is True
    assert rec.tx_hash == tx


def test_inscribe_parses_token_id(ardi_agent):
    tx = "0x" + "ef" * 32
    routes = {
        ("inscribe", "--epoch", "9", "--word-id", "4"): FakeProc(
            stdout=f"minted! token_id: 12345 tx={tx}"
        ),
    }
    rec = ardi_agent(routes).inscribe(epoch=9, word_id=4)
    assert rec.minted
    assert rec.token_id == 12345
    assert rec.tx_hash == tx


def test_commits_pending_json(ardi_agent):
    routes = {
        ("commits", "--json"): FakeProc(
            stdout=json.dumps([{"epoch": 9, "word_id": 4}, {"epoch": 9, "word_id": 7}])
        ),
    }
    pending = ardi_agent(routes).commits_pending()
    assert list(pending) == [(9, 4), (9, 7)]
