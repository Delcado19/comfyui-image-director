# Fixed-E2 result (cold baseline) — 2 reference images, dependency fix, clean idle start

Follow-up to `RESULTS_E2_fixed.md`, which showed the scheduling fix working
(criteria 4/5 restored) but criterion 7 still failing due to a warm-cache
confound (10432 MiB resident from the prior E3 run, not evicted). This run
repeats the same fixed graph from a genuinely idle baseline, obtained via
ComfyUI's own built-in `POST /free {"unload_models": true, "free_memory":
true}` endpoint (`server.py:1192-1201`, confirmed by source read, not
invented) — no restart, no config change, a standard reversible runtime
action. VRAM dropped from 10360 MiB to 1272 MiB within seconds of the call.

Scope: infrastructure/VRAM only. No image-quality, identity, edit-locality,
or prompt-quality conclusions are drawn.

## Run identity

- prompt_id: `24532628-db95-4f05-a449-d7424fa9c4d1`
- Graph: `E2_fixed_cold_graph.json` — identical to `E2_fixed_graph.json`
  except a fresh analyzer seed (20260823, unused before) to avoid any
  cache ambiguity.
- Wall time: 112.95 s (`comfyui.log`) / 113.4 s (`submit_and_monitor.py`) —
  slower than the warm-cache fixed-E2 run (74.70s), because `/free`'s
  `free_memory` flag also resets the executor's own node-output cache
  (`execution.PromptExecutor.reset()`), so loaders 1/2/3 reloaded from
  disk fresh here too (`execution_cached` list was empty — nothing
  reused, confirmed in `submit_result_E2_fixed_cold.json`).
- Output: `E:\AI_Art\ImageDirector_TestE2fixed_cold_00001_.png`, 279,015
  bytes.
- Post-run health: `/system_stats` 200, `/queue` empty, no OOM/traceback in
  the new log lines (one benign informational line containing the
  substring "OOM" — `"Dequantizing token_embd.weight to prevent runtime
  OOM"` — a routine preventive-measure message, not an actual occurrence).

## Log evidence — scheduling order

```
t=+1.07s   [QwenVL] Loading GGUF...              <- analyzer first, again
t=+6.11s   analyzer inference done (3.26s)
t=+13.28s  Requested to load QwenImageTEModel_   <- editor CLIP, only after
t=+15.61s  editor CLIP loaded completely
t=+52.64s  editor unet loaded partially
t=+111.0s  sampler 8/8 done
```

Same corrected order as the warm-cache fixed-E2 run — confirms the fix is
not baseline-dependent.

## VRAM shape (250 ms sampling, 651 samples)

| Phase | Time | Used | Free |
|---|---|---|---|
| Pre-submit idle baseline (5 flat samples via gate check) | t=-8s..0s | 1193 MiB | 14785 MiB |
| Analyzer phase peak | t=+18.0s | ~8664 MiB | ~7314 MiB |
| **Trough — analyzer released, back near idle** | t=+20.3s | **1586 MiB** | **14392 MiB** |
| Editor CLIP load, second smaller dip mid-load | t=+24s..+32s | fluctuates 2895-9035, dips to 1339 | fluctuates, up to 14639 |
| Editor unet load (long steady climb) | t=+38.5s..+53.3s | 1525 -> 14719 MiB | 14453 -> 1259 MiB |
| **Overall peak (sampler plateau)** | t=+65.5s | **14786 MiB** | **1192 MiB** |
| Post-completion, settling | t=+112.9s..+141.4s | 10104-10561 MiB | 5394-5874 MiB |

The trough (1586 MiB) lands within ~400 MiB of the 1193 MiB idle baseline
— essentially a full release, tighter than any prior run's trough
(original E2/E3 never got closer than several GiB above idle; even the
warm fixed-E2 run's trough, while proportionally clean, was 8777 MiB in
absolute terms because it started from 10432 MiB warm).

## Assessment against the 8 criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Graph completes with no node error | PASS |
| 2 | No CUDA OOM | PASS |
| 3 | No server disconnect | PASS |
| 4 | Analyzer and editor peaks as two distinct, non-overlapping plateaus | **PASS** |
| 5 | Visible trough back near idle baseline | **PASS** — 1586 MiB vs. 1193 MiB idle, ~400 MiB gap |
| 6 | SaveImage output exists, non-trivial size | PASS (279,015 bytes) |
| 7 | >= 300 MiB free at peak | **PASS** — 1192 MiB free at the overall peak, 4x the required floor |
| 8 | Reference image count matches intent (2) | PASS (confirmed in graph JSON: `image1`/`image2`, no `image3`) |

**All 8 of 8 criteria pass.** From a clean baseline, the StringSubstring
dependency fix fully resolves what E2/E3 exposed: the analyzer and editor
no longer share VRAM residency, and headroom is comfortable (1192 MiB
free, not a near-miss).

## What this settles vs. what it doesn't

- Settles: the root cause identified in E2/E3 (independent negative-prompt
  node scheduled before the analyzer) is fixed by giving it a real data
  dependency on the analyzer's output. Confirmed twice now (warm and cold
  baseline) via direct log-order evidence, not just VRAM shape inference.
- Settles: from an idle start, 2-reference Analyzer+Editor in one graph,
  one queue press, clears the 300 MiB floor with real margin (1192 MiB).
- Does not settle: whether 3 references (fixed-E3) also clears the floor —
  a separate measurement, not implied by the 2-reference result (E2 vs. E3
  originally showed depth getting worse with reference count, even though
  E3's *cause* was the same bug; the fixed architecture's 3-reference
  headroom is still unmeasured).
- Does not settle: repeat-run consistency (n=1 for this specific graph +
  seed), or behavior starting from a *warm but not-fully-resident* state
  between idle and 10432 MiB (only the two endpoints were tested).
- Infrastructure/VRAM scope only — no quality, identity, or locality claim.
