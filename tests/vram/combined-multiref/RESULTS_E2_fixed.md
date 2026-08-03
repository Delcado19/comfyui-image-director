# Fixed-E2 result — 2 reference images, StringSubstring dependency fix applied

Scope: infrastructure/VRAM only. Tests whether Codex's proposed fix
(force node 8's negative prompt through a `StringSubstring(["16",0], 0, 0)`
node, so it has a real data dependency on the analyzer) restores the
non-overlapping two-phase execution shape that the original E2/E3 lacked.

## Run identity

- prompt_id: `36930bd4-5b17-4e34-940e-083f2d02a5b9`
- Graph: `E2_fixed_graph.json` (16 nodes — E2's 15 plus node "17"
  `StringSubstring`, analyzer seed 20260821, `keep_model_loaded=false`).
  Structurally validated before submit: no dangling links, all class_types
  confirmed live via `/object_info` (`StringSubstring` source read directly
  from `comfy_extras/nodes_string.py` — `execute(cls, string, start, end):
  return io.NodeOutput(string[start:end])`, i.e. `[0:0]` is guaranteed `""`
  regardless of the analyzer's actual text).
- Wall time: 74.70 s (`comfyui.log`) / 75.2 s (`submit_and_monitor.py`) —
  faster than original E2 (122.56s), see "confound" note below.
- Output: `E:\AI_Art\ImageDirector_TestE2fixed_00001_.png`, 888,155 bytes.
- `/history`: `completed=true`, no error. Cached: 1,2,3,4,5,7,10,11,12.
  Node 16 not cached (fresh, seed 20260821 unused before). Node 17
  (new) necessarily not cached either (first time this node exists).

## IMPORTANT METHODOLOGICAL NOTE — warm cache, not idle

The pre-submit gate (queue empty, VRAM flat for 5 samples) passed, but the
flat baseline was **10432 MiB**, not the ~966-1135 MiB idle baseline the
original E2/E3 started from. This is leftover resident state from the E3
run roughly 20 minutes earlier — confirmed still present at the same level
immediately before this run and unchanged for at least 3 more minutes
after this run completed, i.e. not a transient, not decaying on its own.
This matches audit §12's documented behavior: ComfyUI's model cache is
evictable-on-demand, not automatically freed by idle time alone. No
restart or manual unload was performed (out of scope; the mandatory rules
prohibit changing running state beyond what a test needs). This is flagged
as a methodological confound, not a fix result, and is the reason this
run's absolute peak/free numbers cannot be directly compared to the
original cold-start E2's — only the *shape* (ordering, phase separation)
is a clean comparison.

## Log evidence — scheduling order (the actual thing being tested)

```
t=0.0s     got prompt
t=+0.45s   [QwenVL] Loading GGUF: Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf   <- analyzer FIRST
t=+6.77s   [QwenVL] Tokens: ... time=4.11s, speed=80.55 tok/s             <- analyzer done
t=+7.95s   Requested to load QwenImageTEModel_                            <- editor CLIP, only NOW
t=+9.77s   loaded completely; 6222.63 MB loaded
t=+15.81s  loaded partially; unet 12492.21 MB loaded, 76.11 MB offloaded
t=+74.0s   sampler 8/8 done
t=+74.7s   Prompt executed
```

This is the reverse of E2/E3's order, where `Requested to load
QwenImageTEModel_` appeared **before** `[QwenVL] Loading GGUF`. The fix
works exactly as designed: node 8's new dependency on node 16 (via node 17)
prevented the executor from scheduling the editor's CLIP load until the
analyzer had already finished and started releasing.

## VRAM shape — non-overlapping phases restored

| Phase | Time | Used | Free |
|---|---|---|---|
| Pre-submit flat baseline (warm, see note above) | t=-8s..0s | 10432 MiB | 5546 MiB |
| Analyzer phase peak | t=+18.0s | 15855 MiB | 123 MiB |
| **Trough — analyzer released, editor not yet loading** | t=+20.5s | **8777 MiB** | **7201 MiB** |
| Editor CLIP + unet load (noisy climb, own sub-fluctuations) | t=+22s..+30s | climbing to 14697 MiB | dropping to 1281 MiB |
| Editor/sampler phase plateau | t=+34s..+65s | 14857-15036 MiB | 942-1121 MiB |
| Post-completion | t=+74.7s | 10341 MiB | 5637 MiB |

The trough (8777 MiB used, 7201 MiB free) is not just "lower than the two
peaks" — it drops **below the pre-submit warm baseline itself** (10432
MiB), which is a stronger and cleaner separation signal than E2/E3 ever
showed (their post-analyzer floor stayed 10x-40x further from any
baseline). Two distinct peaks are visible: the analyzer's own phase
(~15844-15855 MiB) and a separate, lower editor/sampler phase
(~14857-15036 MiB) — not a single stacked peak.

## Assessment against the same 8 criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Graph completes with no node error | PASS |
| 2 | No CUDA OOM | PASS |
| 3 | No server disconnect | PASS |
| 4 | Analyzer and editor peaks as two distinct, non-overlapping plateaus | **PASS** — restored, confirmed both by log ordering and VRAM shape |
| 5 | Visible trough back near baseline between the two phases | **PASS** — trough (8777 MiB) drops below the pre-submit baseline itself (10432 MiB) |
| 6 | SaveImage output exists, non-trivial size | PASS (888,155 bytes) |
| 7 | >= 300 MiB free at peak | **FAIL** — 123 MiB free at the analyzer-phase peak |
| 8 | Reference image count matches intent (2) | PASS (confirmed in `E2_fixed_graph.json`) |

**7 of 8 criteria now pass — the scheduling fix demonstrably works.**
Criterion 7 still fails, but for a different, distinguishable reason than
in E2/E3: not phase overlap, but this specific run starting from an
already-warm 10432 MiB baseline (leftover E3 residency) instead of idle.
The analyzer's own isolated delta here (~5.4 GiB, 10432->15855) is
consistent with its previously-measured isolated footprint (Test A:
~6.1-6.2 GiB delta from an idle ~1537-1717 baseline) — from a genuinely
idle start, this same delta would land around 6.4-7.3 GiB peak, nowhere
near the ceiling. This run does not establish that the fixed architecture
has adequate headroom from a cold start; it establishes that the
scheduling defect itself is fixed. A clean cold-baseline re-run (or a
repeat measurement after the resident state naturally clears) would be
needed to separately confirm criterion 7 from an unconfounded baseline.

## Explicit limitations

- Single run (n=1).
- Warm-cache confound explained above — criterion 7's failure here should
  not be read as "the fix doesn't solve the VRAM problem"; it's a separate,
  distinguishable effect from residual model-cache state this specific run
  happened to start from.
- Infrastructure/VRAM scope only — no quality, identity, locality, or
  prompt-quality claim.
