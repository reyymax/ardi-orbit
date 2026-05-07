# ardi-orbit · demo recorder

Everything you need to generate a polished demo GIF/MP4 for the
[Xiaomi MiMo 100T grant form](https://100t.xiaomimimo.com/).

## TL;DR

```bash
./demo/install_recorder.sh    # one-time: asciinema + agg
./demo/record.sh              # produces demo/ardi-orbit-demo.{cast,gif,mp4}
```

Upload the `.gif` (or `.mp4`) as **Proof of usage & impact** in the form.

---

## What the demo shows

A fully simulated Ardi WorkNet epoch with:

- **15 real multilingual riddles** (EN · ZH · ID · JA · KO · AR · ES · FR · DE · RU · PT · HI)
- **Solver agent** answering each one with confidence + reasoning
- **Strategy agent** applying confidence threshold + gas budget + per-epoch cap
- **Rich-rendered decision table** showing which riddles get committed
- **Commit / Reveal / Inscribe** phases with realistic tx hashes
- **2 Ardinal NFTs minted** (`token #3358`, `token #3494`) in epoch 142
- Persisted epoch state file

No real network calls — both the LLM and the `ardi-agent` CLI are
mocked deterministically so the recording is reproducible.

---

## Files

| File | Purpose |
|------|---------|
| `demo_data.py` | 15 riddles + canned LLM responses |
| `run_demo.py` | Patches LLM + subprocess, invokes `MonitorAgent.run_epoch()` |
| `install_recorder.sh` | Installs asciinema into `.venv/`, downloads static `agg` binary |
| `record.sh` | Wraps `run_demo.py` in asciinema + converts `.cast → .gif → .mp4` |
| `ardi-orbit-demo.cast` | Raw asciinema recording (git-ignored) |
| `ardi-orbit-demo.gif` | Animated GIF ready for grant upload (git-ignored) |
| `ardi-orbit-demo.mp4` | Optional MP4 (requires `ffmpeg`; git-ignored) |

---

## Customizing

Edit `demo_data.py`:

- **Tweak riddles** — swap in your own favourites; each needs
  `mock_answer`, `mock_confidence`, `mock_reasoning`.
- **Change winner count** — edit `_WINNER_WORD_IDS` in `run_demo.py`.
- **Change speed** — adjust `--speed` in `record.sh` (default `1.3`; try
  `1.0` for slower, `2.0` for snappier).
- **Change theme** — `--theme monokai` → `dracula`, `solarized-dark`,
  `nord`, `github-dark`. Full list: `./demo/bin/agg --help`.

---

## Troubleshooting

### Rich colors look washed out in the GIF

Set in your shell before running `./demo/record.sh`:

```bash
export FORCE_COLOR=3
export COLORTERM=truecolor
```

`record.sh` already does this; only needed if you invoke `asciinema`
directly.

### Unicode glyphs (CJK / Arabic / Devanagari) show as boxes

`agg` uses its bundled font by default. For better CJK / RTL coverage:

```bash
./demo/bin/agg --font-family 'Noto Sans Mono CJK SC,Noto Sans Arabic' \
    demo/ardi-orbit-demo.cast demo/ardi-orbit-demo.gif
```

Install the Noto fonts on Debian/Ubuntu:

```bash
sudo apt-get install -y fonts-noto-mono fonts-noto-cjk fonts-noto-color-emoji
```

### GIF is too big (>20MB grant limit)

Shrink it:

```bash
# Cut the frame rate
./demo/bin/agg --fps-cap 15 --speed 1.5 demo/ardi-orbit-demo.cast out.gif

# Or convert to MP4 (usually 3–10× smaller)
ffmpeg -i demo/ardi-orbit-demo.gif \
    -movflags +faststart -pix_fmt yuv420p \
    -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" \
    demo/ardi-orbit-demo.mp4
```

### Record a **real** live run instead

Flip `dry_run=False` + point `ARDI_AGENT_BIN` at your installed binary,
then record the real `ardi-orbit run` command. (Warning: this costs gas
+ bonds on Base mainnet.)

```bash
export ARDI_ORBIT_DRY_RUN=false
asciinema rec real-run.cast -c ".venv/bin/ardi-orbit run"
```

---

## For the grant reviewers

This demo is **deterministic and reproducible**. You can verify it
yourself:

```bash
git clone https://github.com/reyymax/ardi-orbit
cd ardi-orbit
python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"
./demo/install_recorder.sh
./demo/record.sh
```

Expected: identical `epoch 142` output, 2/5 commits winning VRF,
tokens `#3358` and `#3494` minted.
