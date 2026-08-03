# Fixed-E3 result (clean baseline) — 3 reference images, dependency fix

Formal gated E3 (not a stress-test override this time — the fixed 2-reference
graph passed all 8 criteria from a clean baseline first, per
`RESULTS_E2_fixed_cold.md`, legitimately reopening the gate). Scope:
infrastructure/VRAM only. No image-quality, identity, edit-locality, or
prompt-quality conclusions are drawn.

## Run identity

- prompt_id: `dfe7a9a1-e171-4f01-b869-a47336cc0269`
- Graph: `E3_fixed_graph.json` (17 nodes: E3's 16 plus node "17"
  `StringSubstring`; analyzer seed 20260824, fresh; `keep_model_loaded=false`).
  Structurally validated: node 8 `prompt` -> `["17",0]` -> depends on node
  16; `image1`/`image2`/`image3` present on both `TextEncodeQwenImageEditPlus`
  nodes; no dangling links.
- Pre-run gate: `GET /queue` empty, `POST /free {"unload_models": true,
  "free_memory": true}` called, VRAM flat at 1249 MiB for 5 consecutive
  samples before submit (genuinely idle, not warm).
- Wall time: 122.25 s (`comfyui.log`) / 122.8 s (`submit_and_monitor.py`).
  `execution_cached` empty (same `/free`-driven full cache reset as the
  cold fixed-E2 run) — everything executed fresh.
- Output: `E:\AI_Art\ImageDirector_TestE3fixed_00001_.png`, 1,210,716 bytes.
- Post-run health: `/system_stats` 200, `/queue` empty, no OOM/traceback/
  exception in the new log lines (one benign "...prevent runtime OOM"
  informational line, same as every other run, not an actual occurrence).

## Log evidence — scheduling order

```
t=+1.06s   [QwenVL] Loading GGUF...              <- analyzer first
t=+19.58s  analyzer inference done (8.18s)
t=+26.80s  Requested to load QwenImageTEModel_   <- editor CLIP, only after
t=+29.54s  editor CLIP loaded completely
t=+38.93s  editor unet loaded partially (773.17 MB offloaded)
t=+121.2s  sampler 8/8 done
```

Same corrected order as both fixed-E2 runs — confirmed for the 3-reference
case too.

## VRAM shape (250 ms sampling, 672 samples)

| Phase | Time | Used | Free |
|---|---|---|---|
| Pre-submit idle baseline | t=-8s..0s | 1249 MiB | 14729 MiB |
| Analyzer phase peak | t=+32.8s | ~8517-8929 MiB | ~7049-7461 MiB |
| **Trough — analyzer released, back at idle** | t=+34.0s | **1441 MiB** | **14537 MiB** |
| Editor CLIP load (with one further full dip back to ~1249 mid-load) | t=+41s..+46.7s | fluctuates, dips to 1249 | fluctuates, up to 14729 |
| Editor unet load (steady climb) | t=+47s..+53.5s | 2081 -> 14305 MiB | 14729 -> 1673 MiB |
| **Overall peak (sampler plateau)** | t=+101.7s | **14675 MiB** | **1303 MiB** |
| Post-completion, settling | t=+122.2s..+170.6s | 10312-12840 MiB | 3138-5730 MiB |

**Zero samples (of 672) fell below 300 MiB free anywhere in the entire
run.** The lowest point reached at any time was the overall peak itself,
1303 MiB free — more than 4x the acceptance floor, and worlds apart from
the original E3's 27 MiB absolute minimum with 66 samples under 300 MiB.

## Assessment against the 8 criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Graph completes with no node error | PASS |
| 2 | No CUDA OOM | PASS |
| 3 | No server disconnect | PASS |
| 4 | Analyzer and editor peaks as two distinct, non-overlapping plateaus | **PASS** |
| 5 | Visible trough back near idle baseline | **PASS** — 1441 MiB vs. 1249 MiB idle, ~192 MiB gap (tightest/cleanest trough of any run in this whole test series) |
| 6 | SaveImage output exists, non-trivial size | PASS (1,210,716 bytes) |
| 7 | >= 300 MiB free at peak | **PASS** — 1303 MiB free, never dropped below that anywhere in the run |
| 8 | Reference image count matches intent (3) | PASS (confirmed in graph JSON: `image1`/`image2`/`image3`) |

**All 8 of 8 criteria pass.**

## Comparison across the whole test series (2 vs. 3 references, broken vs. fixed)

| Run | Refs | Fixed? | Baseline | Peak used | Peak free | Criteria passed |
|---|---|---|---|---|---|---|
| E2 | 2 | no | idle (~1056) | 15866 | 112 | 5/8 |
| E3 | 3 | no | idle (~966) | 15951 | **27** | 5/8 |
| Fixed-E2 (warm) | 2 | yes | warm (10432) | 15855 | 123 | 7/8 (7 failed — confound, see below) |
| Fixed-E2 (cold) | 2 | yes | idle (1193) | 14786 | 1192 | **8/8** |
| Fixed-E3 (cold) | 3 | yes | idle (1249) | 14675 | **1303** | **8/8** |

The fix does not just marginally help — it changes the failure mode
entirely. Unfixed, adding a reference image made the margin *worse* (112
-> 27 MiB). Fixed and cold-started, adding a reference image left the
margin roughly the same or slightly *better* (1192 -> 1303 MiB).
**Correction (caught by Codex in joint review, verified against the raw
CSV):** an earlier draft of this section wrongly attributed this to the
analyzer being "the binding constraint at peak" — it is not. In both cold
fixed runs, the analyzer's own phase peaks much lower (~8517-8929 MiB) and
fully releases; the run's actual overall/binding peak occurs later, during
the editor/sampler phase (14786 MiB for fixed-E2-cold, 14675 MiB for
fixed-E3-cold). The correct statement: once the fix removes the
analyzer/editor overlap, the third reference image only affects the later,
already-isolated editor phase — and in this single run, that editor peak
happened to land close to fixed-E2-cold's (comparable, not identical;
n=1 per condition, not a proven invariant).

## What this settles

- The root-cause fix (forcing node 8's dependency on the analyzer via
  `StringSubstring`) is confirmed working for both 2 and 3 reference
  images, from a clean baseline, with real safety margin, not a near-miss.
- The catastrophic low-headroom failure seen in unfixed E2/E3 (112 MiB,
  then 27 MiB) was caused by analyzer/editor scheduling overlap, not by
  the third reference image alone — that is the defensible claim; "more
  references never matters" is not established by two single runs.
- A `/free` preflight (ComfyUI's own built-in endpoint) is sufficient to
  obtain a clean baseline without a server restart, and is cheap/fast
  (VRAM drops within seconds).

## What this does not settle

- Whether a *production* Image Director workflow needs to call `/free`
  before every run, or some other warm-cache policy, to guarantee this
  margin holds under repeated real-world use (only the two endpoints -
  fully warm, fully cold - were tested; nothing in between).
- Any image-quality, identity-preservation, edit-locality, or
  prompt-quality claim — this remains purely infrastructure/VRAM evidence.
- Single run per condition (n=1 each); no repeat-run variance data for the
  fixed graphs specifically (though the pattern across 5 different runs in
  this series, unfixed and fixed, cold and warm, is internally consistent
  enough to trust qualitatively).
- Whether the `StringSubstring` fix is the only viable fix, or the best
  one architecturally (e.g. an explicit unload/offload node between
  analyzer and editor, per audit §10's "candidate 2", was not tested here
  and remains a valid alternative).
