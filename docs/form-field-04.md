# Form Field 04 — "Describe what you've built with agents or AI driven workflows"

Tiga versi dgn panjang berbeda. Pake yg paling cocok dgn form's char limit
(biasanya 2000–4000 chars). Kalo ragu, pake **versi B (default)**.

---

## ▶ Versi A — Punchy (≈900 chars)

I built **ardi-orbit** — a four-agent autonomous mining loop for the Ardi WorkNet (a sub-network of the AWP protocol on Base mainnet). The official `ardi-skill` Rust CLI exposes commit/reveal/inscribe primitives but ships *no actual agent*; its README explicitly says "agent IS the LLM; skill = tool". `ardi-orbit` is that missing agent layer.

Each epoch the loop runs: **(1)** `SolverAgent` reasons about 15 multilingual riddles (EN/ZH/ID/JA/KO/AR/ES/FR/DE/RU/PT/HI) producing answer + calibrated confidence + chain-of-thought; **(2)** `StrategyAgent` filters by confidence threshold and gas budget, with an LLM that may VETO commits but never promote (so a bad LLM call cannot forfeit ETH); **(3)** `ExecutorAgent` drives `commit → wait → reveal → wait → inscribe` on Base, gating each phase on the previous; **(4)** `MonitorAgent` orchestrates, persists state, and resumes cleanly after crashes.

Provider-agnostic via litellm — defaults to MiMo v2.5 Reasoner, swaps to Claude/GPT with one env var. 24 unit tests, ruff-clean, MIT.

Repo: <https://github.com/reyymax/ardi-orbit>

---

## ▶ Versi B — Default (≈2400 chars) ⭐ RECOMMENDED

I built **`ardi-orbit`**, a four-agent autonomous mining loop for the **Ardi WorkNet** — a riddle-solving sub-network of the AWP protocol that mints "Ardinal" NFTs (1 of 21,000) on Base mainnet. The official `ardi-skill` Rust CLI exposes commit/reveal/inscribe primitives but ships *no actual agent*; its own README states the design rule: *"agent IS the LLM; skill = tool"*. `ardi-orbit` is the production-quality reference implementation of that rule.

**The agent loop (one full epoch):**

1. **`SolverAgent`** fetches 15 riddles in 12 languages (EN, ZH, ID, JA, KO, AR, ES, FR, DE, RU, PT, HI), detects the source language, reasons in-language to avoid English-fallback drift, then normalizes the answer to a canonical form. Returns a structured `(answer, confidence, reasoning, alternates)` via JSON-mode with a 3-attempt retry on schema-failure.

2. **`StrategyAgent`** runs a deterministic baseline (confidence threshold, gas budget computed from current ETH balance, max-commits-per-epoch cap) and then asks an LLM for *refinement*. Critical safety property: the LLM can **veto** a commit but cannot **promote** a low-confidence one. This means a hallucinating model can lose at most an opportunity, never the wallet.

3. **`ExecutorAgent`** drives `ardi-agent commit` → wait ~35s for the commit window → `reveal` → wait ~35s for Chainlink VRF → `inscribe` on each VRF winner. Each phase is gated on the previous (only reveal confirmed commits, only inscribe winners), with parsed tx hashes / token IDs / win flags.

4. **`MonitorAgent`** is the orchestrator. It persists every epoch's full state to `~/.ardi-orbit/epoch-NNNNNN.json` and exposes `recover` to resume after crashes — bonds are never forfeit due to the wrapper failing.

**Why MiMo specifically:** non-Latin riddles (classical Chinese 谜语, Japanese なぞなぞ, Arabic ألغاز) require multilingual chain-of-thought without English-fallback drift. MiMo v2.5 Reasoner handles this natively, and the OpenAI-compatible API drops in via `litellm` — so the same code transparently runs on Claude / GPT / Gemini.

**Production quality:** 24 unit tests, ruff-clean, MIT-licensed, dry-run mode, crash recovery, gas-aware budgeting, soft-fail LLM refinement. Includes a self-contained reproducible demo (`./demo/record.sh`) that exercises the full pipeline offline — generates a deterministic GIF showing epoch 142 with 5 commits, 2 VRF wins, and tokens #3358 and #3494 minted.

Repo: <https://github.com/reyymax/ardi-orbit>

---

## ▶ Versi C — Long-form (≈4000 chars)

(Use this if the form has a 4000–5000 char limit and you want to flex.)

### Project: `ardi-orbit` — autonomous LLM agent loop for the Ardi WorkNet

I built `ardi-orbit`, a Python multi-agent orchestration system that turns the official `ardi-skill` Rust CLI into a fully autonomous, self-driving NFT mining loop on Base mainnet. The Ardi WorkNet (sub-network of the broader AWP protocol) requires solving 15 multilingual riddles every epoch and committing answers on chain with a small ETH bond, which is forfeit if the answer is wrong on reveal. Winners (selected by Chainlink VRF) get to inscribe an Ardinal NFT (1 of 21,000 total). The skill itself is intentionally agent-less — its README states *"agent IS the LLM; skill = tool"* — making it a perfect substrate for an agentic workflow.

### The four-agent architecture

**`SolverAgent` — multilingual reasoning.** For each of the 15 riddles per epoch, the solver detects the source language (EN/ZH/ID/JA/KO/AR/ES/FR/DE/RU/PT/HI), reasons in-language using a language-aware system prompt that explicitly instructs the model not to fall back to English mid-thought, and returns `(answer, confidence∈[0,1], reasoning, alternates, detected_language)` via JSON-schema validation. Three-attempt retry on malformed output, configurable model (default MiMo v2.5 Reasoner).

**`StrategyAgent` — confidence-and-gas-aware commit selection.** This is the safety-critical agent: each commit locks ~0.005 ETH that's lost if the answer is wrong, so we cannot be greedy. The strategy first computes a deterministic baseline (skip below 0.75 confidence, cap by `max_commits_per_epoch`, cap by `gas_eth ÷ estimated_commit_cost`). It then asks an LLM to refine the ranking — but with a hard rule: the LLM can **only veto** commits, never **promote** low-confidence ones. This soft-fail design means even a fully hallucinating refinement model can at most cost us an opportunity, never the wallet.

**`ExecutorAgent` — chain coordinator.** Wraps `ardi-agent commit/reveal/inscribe` via subprocess. Each phase is gated on the previous: reveal only runs against confirmed commits; inscribe only runs against VRF winners. Parses tx hashes, token IDs, win flags. Has a dry-run mode that exercises the full code path without sending transactions, used by both tests and the demo.

**`MonitorAgent` — orchestrator + state.** Top-level coordinator that runs preflight → context fetch → solve → strategize → commit → wait (~35s commit window) → reveal → wait (~35s VRF) → inscribe → persist. Every epoch's complete state (riddles, attempts, decisions, tx receipts) is dumped to `~/.ardi-orbit/epoch-NNNNNN.json`. The `recover` subcommand walks pending commits after a crash and reveals/inscribes whatever it can — bonds are never forfeit because the wrapper failed.

### Multi-step reasoning per epoch

A real epoch makes **15 solver LLM calls + 1 strategy LLM call + N×3 on-chain transactions** (commit, reveal, inscribe), with timed waits between phases for the commit window to close and for Chainlink VRF to fulfill. This is genuinely multi-step, not a single prompt.

### Why MiMo

Non-Latin riddles — classical Chinese 谜语, Japanese なぞなぞ, Arabic ألغاز, Hindi पहेली — break down on models that quietly fall back to English mid-reasoning. MiMo v2.5 Reasoner handles in-language CoT cleanly. The OpenAI-compatible API drops into litellm, so swapping providers is one env var.

### Production quality

- **24 unit tests**, all green, mocked subprocess + LLM (no chain or API needed in CI)
- **Ruff-clean**, full type hints, MIT-licensed
- **Self-contained reproducible demo** (`./demo/record.sh`) — generates a deterministic asciinema/GIF showing epoch 142 with 5 commits, 2 VRF wins, tokens #3358 and #3494 minted
- **Dry-run mode** for offline rehearsal
- **Crash recovery** via `ardi-orbit recover`
- **Gas-aware budgeting** so we never run out mid-epoch

Repo: <https://github.com/reyymax/ardi-orbit>
Demo GIF: included in repo at `demo/ardi-orbit-demo.gif`
