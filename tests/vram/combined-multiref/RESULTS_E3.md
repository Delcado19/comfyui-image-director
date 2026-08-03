# Test E3 result — 3 reference images, analyzer + editor, one graph

**Status: user-overridden stress test, not the originally gated E3
acceptance test.** The approved test plan (`TESTPLAN.md`) required E2 to
pass all 8 acceptance criteria before E3 could run. E2 failed 3 of 8
(#4, #5, #7 — see `RESULTS_E2.md`). The user explicitly instructed running
E3 anyway after being shown the E2 failure and the stop condition. Codex
concurred with proceeding under this explicit override, on the condition
that the graph stays unmodified and this run is labeled as a stress test,
not a passed gate. Scope is still infrastructure/VRAM only — no
image-quality, identity, edit-locality, or prompt-quality conclusions are
drawn.

## Run identity

- prompt_id: `c7372e76-97ab-406a-9077-6e06dd6f2fa7`
- Graph: `E3_graph.json` (16 nodes, analyzer seed 20260802, `keep_model_loaded=false`) — unmodified from the version Codex structurally reviewed before E2.
- Reference images: source (`imgdir_test_source.png`, analyzer input + editor `image1`), `imgdir_test_ref2.png` (editor `image2`), `imgdir_test_ref3.png` (editor `image3`, green RGB 60/180/90) — 3 reference images, confirmed directly in the submitted graph JSON.
- Wall time: 116.87 s (`comfyui.log`) / 117.4 s (`submit_and_monitor.py`).
- Output: `E:\AI_Art\ImageDirector_TestE3_00001_.png`, 481,610 bytes — exists, non-trivial size. No content/quality judgement made or implied.
- `/history` status: `completed=true`, no `execution_error`. Cached nodes: 1,2,3,4,5,7,10,11,12 (loaders/scale/VAEEncode/ref2-image — expected, all identical to a prior run). Node 16 (analyzer) NOT cached — cache-bust via distinct seed (20260802) confirmed working again.
- Pre-run gate: queue empty; a separate manual `nvidia-smi` check (5 samples, taken just before starting the CSV logger) showed 966 MiB flat; the CSV logger's own first samples read 1066 MiB flat (a few seconds earlier in the same idle window, different measurement instant, not a contradiction) — either way, comfortably below E2's 1056 MiB baseline, no warm-cache contamination from E2. Server responded 200 to `/system_stats` before submit.
- Post-run health check: server still responds (`/system_stats` 200, `/queue` empty). Two separate post-run VRAM readings: the CSV logger's own tail settled at a stable 10137 MiB (last ~10 samples, `vram_log_E3.csv`); a separate manual `nvidia-smi` check taken ~20s after stopping the logger read 10268-10273 MiB (slightly later point in time, consistent with the same general resident-cache order of magnitude as E2's and the original audit's post-run state, not the same instant as the CSV tail). No OOM/traceback/exception string found in the new `comfyui.log` lines.

## VRAM time series (250 ms sampling, `vram_log_E3.csv`, 641 samples)

Correlated against `G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log`
(`comfyui_log_excerpt_E3.txt`).

| Event | Wall time | VRAM used | VRAM free |
|---|---|---|---|
| Pre-submit flat baseline (5 consecutive samples) | t=-8s..0s | 966 MiB | 15012 MiB |
| `got prompt` | t=0.0s | 960 MiB | 15018 MiB |
| Editor's own CLIP requested | t=+1.75s | 11838 MiB | 4140 MiB |
| Editor's own CLIP loaded completely (6222.63 MB) | t=+4.86s | 14198 MiB | 1780 MiB |
| Analyzer GGUF load start | t=+6.12s | 13848 MiB | 2130 MiB |
| **Sustained near-OOM window** — <300 MiB free for ~16.5s straight, most of it <50 MiB free | t=+6.7s..+23.3s | 15856-15951 MiB | mostly 27-122 MiB |
| **Absolute peak** (single 250ms sample) | t=+10.5s | **15951 MiB** | **27 MiB** |
| Analyzer inference done (14.91 s, 10.06 tok/s) | t=+23.3s | 15943 MiB | 35 MiB |
| Analyzer unload step 1 (1477 MB freed) | t=+24.5s | 11569 MiB | 4409 MiB |
| Analyzer unload step 2 (502 MB freed, 4326.69 MB remains loaded); also the trough minimum in this window | t=+25.6s | **11281 MiB** | **4697 MiB** |
| Editor unet loaded ("partially", 665.10 MB offloaded — 9x more offload than E2's 73 MB) | t=+33.1s | 12497 MiB | 3481 MiB |
| Sampler 8/8 steps done (82.0s, 10.34 s/it — vs. E2's 56s/7.08s/it, ~46% slower) | t=+115.9s | 12707 MiB | 3271 MiB |
| `Prompt executed in 116.87 seconds` | t=+116.9s | 10078 MiB | 5900 MiB |

66 of 641 samples show less than 300 MiB free, and these are fully
contiguous (verified: every one of the 66 samples is adjacent to the next
in the series, no gaps) — a single unbroken 16.552-second block from
22:24:39.304 to 22:24:55.856. This is not a brief, easily-missed spike —
the 250ms sampling directly observed a sustained near-OOM state, not just
one lucky/unlucky sample.

## What this shows

The same overlap bug identified in E2 reproduced identically: the editor's
own CLIP loaded and became fully resident (6222.63 MB, matching E2 exactly)
before the analyzer even started loading its GGUF, and stayed resident
through the analyzer's entire inference. With a third reference image
added, the combined resident footprint during the analyzer's run pushed to
15856-15951 MiB, leaving as little as 27 MiB free (0.17% of the card's
16303 MiB) — an order of magnitude tighter than E2's already-failing 112
MiB.

This 27 MiB near-miss happened entirely during the analyzer's own inference
window (before any editor unet loading starts) and survived on its own,
without any offload help — the automatic low-VRAM/offload path
(665.10 MB offloaded, vs. 73.31 MB in E2) only engaged later, when the
editor's own unet loaded (t=+33.1s, well after the analyzer had already
finished and partially unloaded). That offload is a separate, later
mitigation for the editor's own load pressure, not what got the analyzer
phase's 27 MiB moment through — it explains why the *sampler* phase ran
~46% slower (10.34 s/it vs. 7.08 s/it), not why the earlier near-OOM peak
didn't cross the line. The analyzer-phase peak surviving at 27 MiB appears
to be plain allocator margin, not a designed or even an automatic safety
mechanism.

No CUDA OOM occurred. No node reported an error. The server remained
healthy and responsive after completion. This was not a designed safety
margin — it is a single successful run that came within 27 MiB of the
card's total capacity, on hardware where the audit's own §12 already
documented run-to-run allocator noise on the order of several hundred MiB
(D2 vs. D3's own peak/free numbers were not monotonic). A repeat run with
even slightly different allocator behavior, a marginally larger analyzer
response, or a different image content could plausibly tip this into an
actual OOM. This run's success is evidence the path *can* complete, not
evidence that it *reliably* completes.

## Assessment against the same 8 criteria (for comparability with E2 — not a formal gate, since this was a stress test)

| # | Criterion | Result |
|---|---|---|
| 1 | Graph completes with no node error | PASS |
| 2 | No CUDA OOM | PASS — but see margin: 27 MiB free, an order of magnitude tighter than E2's already-failing 112 MiB |
| 3 | No server disconnect | PASS — confirmed via post-run health check |
| 4 | Analyzer and editor peaks as two distinct, non-overlapping plateaus | **FAIL** — same overlap mechanism as E2, editor CLIP resident throughout |
| 5 | Visible trough back near pre-submit idle baseline between the two phases | **FAIL** — trough minimum 11667 MiB used (4311 free), ~10.7 GiB above the 966 MiB idle baseline |
| 6 | SaveImage output exists, non-trivial size | PASS (481,610 bytes, verified on disk) |
| 7 | >= 300 MiB free at peak | **FAIL** — 27 MiB free at absolute peak, and <300 MiB free for ~16.5s continuously |
| 8 | Reference image count in submitted graph matches intent (3) | PASS (confirmed in `E3_graph.json`) |

**Result: same 3 criteria fail as E2 (#4, #5, #7), with a substantially
worse margin on #7 (27 MiB vs. 112 MiB).** E3's critically-low window
(16.552s continuous, <300 MiB free) is actually shorter than E2's
sustained-plateau window (21s at a less extreme 112 MiB) — duration is not
worse, but depth is: E3's absolute minimum (27 MiB) is much closer to the
true hardware ceiling than E2's (112 MiB). The run completed successfully
this time, but "completed" and "safe" are not the same claim — this is
exactly the kind of near-miss the original 300 MiB acceptance floor was
designed to catch before it turns into an actual failure on a less
favorable run.

## Explicit limitations

- Single run (n=1). No repeat was performed to check how consistently this
  margin holds — given the audit's own documented allocator noise between
  otherwise-identical runs (§12, D2/D3), the 27 MiB figure should be read
  as "this run's measured minimum," not a guaranteed worst case in either
  direction.
- Same scheduling-order mechanism as E2 (source-confirmed by Codex in the
  E2 review) is assumed to apply here too — not re-verified against the
  executor source specifically for the 3-image case, though the log
  evidence (CLIP loads before analyzer GGUF, identical to E2) is
  consistent with the same cause.
- Infrastructure/VRAM scope only; no quality, identity, or locality claim.
- This was explicitly a user-overridden stress test outside the original
  approved gate, run once, and should not be read as "3-reference
  Analyzer+Editor is validated" — the opposite: it demonstrates the
  failure margin is worse than E2's, not that the architecture is safe at
  this reference count.
