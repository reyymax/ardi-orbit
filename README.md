# ardi-orbit

**LLM-driven autonomous mining agent for the [Ardi WorkNet](https://github.com/awp-worknet/ardi-skill).**

`ardi-orbit` wraps the official `ardi-agent` Rust CLI in a four-agent
Python orchestration loop. It reads each epoch's 15 multilingual riddles,
reasons about them with a frontier LLM (default: Xiaomi MiMo v2.5
Reasoner), decides which answers are confident enough to bond on chain,
then drives the full **commit → reveal → inscribe** lifecycle on Base
mainnet to mint Ardinal NFTs (1 of 21,000).

> **Why this exists.** `ardi-skill`'s README states the design rule
> plainly: *"the agent IS the LLM; skill = tool"*. `ardi-orbit` is a
> reference implementation of that rule — a real, schedulable agent loop
> you can point at any OpenAI-compatible endpoint.

---

## Demo

![ardi-orbit demo](demo/ardi-orbit-demo.gif)

Generate the demo yourself (no API keys, no `ardi-agent` binary required):

```bash
./demo/install_recorder.sh    # one-time: installs asciinema + static agg
./demo/record.sh              # produces demo/ardi-orbit-demo.{cast,gif}
```

Expected: a ~30s recording of epoch 142 — 15 riddles solved in 12 languages,
5 commits, 2 VRF wins, 2 Ardinals minted (`#3358`, `#3494`). See
[`demo/README.md`](demo/README.md) for details.

---

## Highlights

- **Multi-agent architecture** — Solver, Strategy, Executor, Monitor.
  Each has a single, testable responsibility.
- **Multilingual reasoning** — handles riddles in EN/ZH/ID/JA/KO/AR/ES/
  FR/DE/RU/PT/HI with language-aware prompts.
- **Calibrated confidence** — solver returns probabilities; strategy
  only commits above a configurable threshold (default 0.75).
- **Gas-aware** — strategy caps per-epoch commits by remaining ETH
  balance to avoid running out mid-window.
- **Soft-fail LLM refinement** — strategy uses a deterministic baseline;
  the LLM can only **veto** a commit, never promote a low-confidence one.
- **Dry-run mode** — exercise the full loop without sending a single
  on-chain transaction.
- **Resume / recovery** — `ardi-orbit recover` walks pending commits and
  reveals/inscribes them. Bond is never forfeit due to the wrapper.
- **Provider-agnostic** — built on [litellm](https://github.com/BerriAI/litellm),
  swap MiMo / Claude / GPT / Gemini with one env var.

---

## Architecture

```
                                ┌──────────────────────┐
                                │   MonitorAgent       │
                                │   (orchestrator)     │
                                └──────────┬───────────┘
                                           │
       ┌──────────────┬──────────────┬────┴─────┬───────────────┐
       ▼              ▼              ▼          ▼               ▼
┌────────────┐  ┌────────────┐  ┌──────────┐ ┌──────────┐  ┌──────────┐
│  ArdiAgent │  │SolverAgent │  │StrategyAg│ │ExecutorAg│  │  state/  │
│  (CLI)     │  │  (LLM)     │  │  (LLM+H) │ │  (CLI)   │  │  (json)  │
└────────────┘  └────────────┘  └──────────┘ └──────────┘  └──────────┘
       │              │              │            │
       │ context()    │              │            │ commit()
       │              │ solve()      │ decide()   │ reveal()
       │              │              │            │ inscribe()
       ▼              ▼              ▼            ▼
   ardi-agent     LLM (MiMo /    LLM + rules    ardi-agent
   binary         Claude / GPT)  (deterministic   binary
                                  baseline)
```

Per-epoch flow:

1. **`preflight()`** — wallet, AWP registration, coordinator, gas, stake
2. **`context()`** — fetch the 15 riddles for this epoch
3. **`solve_all()`** — Solver agent answers each one with reasoning + confidence
4. **`decide()`** — Strategy agent picks the top-N within gas + confidence budget
5. **`commit_all()`** — Executor calls `ardi-agent commit` for each pick
6. *wait ~35s for commit window close*
7. **`reveal_all()`** — Executor calls `ardi-agent reveal`
8. *wait ~35s for Chainlink VRF*
9. **`inscribe_winners()`** — mint NFTs for VRF winners
10. **persist** — full epoch state written to `~/.ardi-orbit/epoch-NNNNNN.json`

---

## Install

### 1. Install `ardi-agent` (the underlying skill)

```bash
curl -fsSL https://raw.githubusercontent.com/awp-worknet/ardi-skill/main/install.sh | sh
```

### 2. Install `awp-wallet`

```bash
git clone https://github.com/awp-core/awp-wallet ~/awp-wallet \
  && cd ~/awp-wallet && bash install.sh awp-wallet setup
```

### 3. Install ardi-orbit

```bash
git clone <this-repo> ardi-orbit && cd ardi-orbit
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Configure

Copy `.env.example` → `.env` and fill in:

```bash
# Xiaomi MiMo (OpenAI-compatible)
MIMO_API_KEY=sk-...
MIMO_API_BASE=https://platform.xiaomimimo.com/v1

ARDI_ORBIT_SOLVER_MODEL=openai/mimo-v2.5-reasoner
ARDI_ORBIT_STRATEGY_MODEL=openai/mimo-v2.5-flash

ARDI_ORBIT_MIN_CONFIDENCE=0.75
ARDI_ORBIT_MAX_COMMITS_PER_EPOCH=5
ARDI_ORBIT_DRY_RUN=true   # flip to false for live mining
```

Want to use Claude or GPT instead? Just change the model name:

```bash
ARDI_ORBIT_SOLVER_MODEL=anthropic/claude-sonnet-4-5
# or
ARDI_ORBIT_SOLVER_MODEL=openai/gpt-4o
```

---

## Usage

```bash
# Sanity check the binary + wallet + chain are wired up
ardi-orbit preflight

# DRY-RUN a full epoch (no on-chain calls)
ardi-orbit run --dry-run

# Live mine one epoch
ardi-orbit run --no-dry-run

# Stop after commit (don't reveal/inscribe yet — useful for cron splits)
ardi-orbit run --skip-reveal

# Resume any pending commits (e.g. after a crash)
ardi-orbit recover

# Inspect a persisted epoch
ardi-orbit show 42
```

Run forever (next-epoch polling every 60s):

```bash
ardi-orbit run --no-once
```

---

## Costs

Inherits the budget from `ardi-skill`:

- **Gas + bonds**: ~0.05 ETH on Base mainnet covers 5–10 days of normal use
- **Stake**: 10,000 AWP allocated to Ardi worknet (or KYA-delegated path)
- **LLM**: ~1k tokens per riddle × 15 riddles × 1 epoch ≈ 15k tokens. With
  MiMo Token Plans this is effectively free during the 100T grant period.

---

## Development

```bash
# Run tests (no chain, no LLM — everything is mocked)
pytest -q

# Lint
ruff check src tests

# Type check
mypy src
```

The test suite covers:

- CLI subprocess wrapper (preflight, context, commit, reveal, inscribe, commits-pending)
- Solver agent (normalization, error handling, batch)
- Strategy agent (confidence threshold, gas budget, max-per-epoch, LLM veto, soft-fail)
- Executor agent (dry-run vs live, gating on confirmed/won)
- End-to-end MonitorAgent.run_epoch (mocked subprocess + mocked LLM)

---

## License

MIT — same as the underlying `ardi-skill`.
