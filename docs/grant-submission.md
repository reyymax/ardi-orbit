# Xiaomi MiMo 100T Grant — Submission Template

Use this as a starting point for the form at <https://100t.xiaomimimo.com/>.
Fields below match the form fields shown on the live page (as of May 2026).

---

## 01 · Your email

`<your-github-linked-email@example.com>`

> Use the email tied to your GitHub account and your MiMo platform
> account. If they don't match yet, bind the email at <https://id.mi.com>
> *before* you submit.

---

## 02 · Which agent tool do you use most?

**Hermes Agent** *(or whichever you actually used to build this)*

> Be honest. Reviewers can tell from commit history / terminal logs.

---

## 03 · Primary model series you use

**MiMo** *(if you ran the loop against MiMo)*, with fallback Claude/GPT.

---

## 04 · Describe what you've built

Paste a tightened version of the following — adjust to match your real
deployment numbers:

```
Project: ardi-orbit — autonomous LLM agent loop for the Ardi WorkNet
Repo:    https://github.com/<you>/ardi-orbit
Stack:   Python 3.11, litellm (provider-agnostic), pydantic v2, typer, rich

Core problem
  The Ardi WorkNet (sub-WorkNet of AWP) ships ardi-skill — a Rust CLI
  whose explicit design rule is "agent IS the LLM; skill = tool". The
  skill exposes commit/reveal/inscribe primitives but ships no actual
  agent. ardi-orbit is that missing piece: a four-agent Python loop
  that drives ardi-skill end-to-end on Base mainnet.

Crew / agent flow
  1. SolverAgent  — reads each epoch's 15 multilingual riddles
                    (EN/ZH/ID/JA/KO/AR/ES/FR/DE/RU/PT/HI), produces
                    answer + calibrated confidence + reasoning trace.
                    JSON-schema output via litellm; 3-attempt retry
                    on malformed output.
  2. StrategyAgent — deterministic baseline (confidence threshold +
                     gas budget + per-epoch cap) refined by an LLM
                     that may VETO commits but never promote. Models
                     a soft-fail policy so a bad LLM call cannot
                     forfeit ETH.
  3. ExecutorAgent — wraps `ardi-agent commit/reveal/inscribe`,
                     parses tx hashes / token IDs / win flags, and
                     gates each phase on the previous one (only
                     reveal confirmed commits, only inscribe winners).
  4. MonitorAgent  — epoch-level orchestrator with timed waits for
                     commit-window close + Chainlink VRF, automatic
                     state persistence to ~/.ardi-orbit, and
                     `recover` to resume after crashes (so bonds
                     are never forfeit due to wrapper failures).

  Multi-step reasoning per epoch:
    preflight → context → solve_all (15× LLM) → decide (1× LLM +
    rules) → commit (N× tx) → wait → reveal (N× tx) → wait → inscribe
    (W× tx) → persist.

Multilingual reasoning is non-trivial: the same riddle protocol mixes
classical Chinese 谜语, Indonesian teka-teki, Japanese なぞなぞ,
Arabic ألغاز, etc. Solver detects language, reasons in-language,
then normalizes the answer to lowercase canonical form.

Why MiMo specifically
  - MiMo v2.5 reasoner handles multilingual chain-of-thought without
    English fallback drift, which matters for non-Latin riddles.
  - OpenAI-compatible API drops in via litellm with one env var.
  - Token Plan pricing makes the 15-riddle/epoch cadence economic.
```

---

## 05 · Proof of usage & impact

Upload **all** of the following (the form takes up to 5 files, ≤20MB each):

### A. AI platform billing screenshot (last 30 days)

- Anthropic / OpenAI / MiMo dashboard showing token spend on this project
- Tag the project name in the description if your provider supports it

### B. Terminal logs / agent workflow recording

Capture an end-to-end run with [asciinema](https://asciinema.org):

```bash
asciinema rec ardi-orbit-demo.cast \
  -c "ardi-orbit run --dry-run --log-level DEBUG"
```

Upload the `.cast` file directly or convert to MP4:

```bash
agg ardi-orbit-demo.cast ardi-orbit-demo.gif
ffmpeg -i ardi-orbit-demo.gif ardi-orbit-demo.mp4
```

### C. Strategy decision table screenshot

After running an epoch you'll see a Rich-rendered decision table that
shows for each riddle: language, answer, confidence, commit/skip,
rationale. Screenshot that — reviewers love this kind of transparency.

### D. On-chain proof (the killer evidence)

For any **live** epoch, copy the BaseScan links of:

- Commit txs
- Reveal txs
- Inscribe (mint) txs
- Resulting Ardinal NFT token IDs

A short markdown table works:

```
Epoch  | Phase     | Tx                          | Result
-------|-----------|-----------------------------|------------------
  142  | commit    | https://basescan.org/tx/0x..| bond 0.005 ETH
  142  | reveal    | https://basescan.org/tx/0x..| won
  142  | inscribe  | https://basescan.org/tx/0x..| token #4521 minted
```

### E. Cost / impact dashboard

A one-pager spreadsheet or screenshot of the persisted
`~/.ardi-orbit/epoch-NNNNNN.json` files showing:

- Tokens used per epoch
- Win-rate by language
- Mint count
- ETH spent vs ETH-equivalent value of NFTs minted

---

## 06 · GitHub project link or live demo URL

```
https://github.com/<you>/ardi-orbit
```

Pin the repo. Make sure the README renders cleanly. Add a short demo GIF
at the top.

---

## Pre-submit checklist

- [ ] Email matches your MiMo platform account (or you've bound it)
- [ ] Repo is public and has a `LICENSE` file
- [ ] `pytest -q` passes locally
- [ ] At least one **real** epoch run logged (live or extensive dry-run)
- [ ] BaseScan links verified (if live)
- [ ] Asciinema recording uploaded
- [ ] Spend screenshot from last 30 days included
- [ ] Submitted before the countdown ends (~21 days remaining as of May 7, 2026)
