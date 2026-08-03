# Combined multi-reference VRAM smoke test (E2 / E3)

Status: PLAN, pending Codex review before execution.
Scope: infrastructure / VRAM only. No image-quality, identity, or edit-locality
claims are in scope for this test (project evidence rules).

## Baseline being extended

Test C (`docs/source/IMAGE_DIRECTOR_AUDIT.md` §13): one API-format graph,
one queue press, `AILab_QwenVL_GGUF_Advanced` (Qwen2.5-VL-7B GGUF analyzer,
`keep_model_loaded=false`) -> its `STRING` output wired directly into
`TextEncodeQwenImageEditPlus`'s positive `prompt` input -> the minimal Qwen
Image Edit 2509 GGUF pipeline from Test B (1 reference image).

E2/E3 change exactly one thing relative to Test C: the number of reference
images at the editor stage (`image2`, `image3` on `TextEncodeQwenImageEditPlus`),
matching Test D2 (2 refs) / D3 (3 refs) from §12. Everything else — analyzer
model/settings, editor model/CLIP/VAE, resolution behavior
(`FluxKontextImageScale`), sampler/scheduler/steps/CFG/denoise, the editor's
own `KSampler` seed, ComfyUI start parameters — is held constant at Test C's
/ Test B's values. The one deliberate exception is the analyzer node's own
`seed` input, which is intentionally varied per run (not held constant) to
force a fresh execution instead of a ComfyUI node-output cache hit — see
"Node-cache bust" below. This does not affect the VRAM measurement; it only
guarantees the analyzer actually runs.

## Graph (`build_graph.py`)

Live-verified against the running server's `/object_info` before writing
this plan (all classes exist, all model paths resolve in the current
dropdowns):

```
LoadImage(imgdir_test_source.png)  [node 4]
  +-> AILab_QwenVL_GGUF_Advanced [node 16]   (analyzer; keep_model_loaded=False)
  |     STRING output -> node 9 "prompt" (positive)
  +-> FluxKontextImageScale [node 7] -> image1 on both node 8 (negative) and node 9 (positive)

LoadImage(imgdir_test_ref2.png) [node 5]     -> image2 on nodes 8 and 9  (E2, E3)
LoadImage(imgdir_test_ref3.png) [node 6]     -> image3 on nodes 8 and 9  (E3 only)

UnetLoaderGGUF [1] -> CFGNorm [10] -> ModelSamplingAuraFlow [11] -> KSampler [13]
CLIPLoaderGGUF [2] -> TextEncodeQwenImageEditPlus negative [8] (prompt="")
                   -> TextEncodeQwenImageEditPlus positive [9] (prompt=<-node 16>)
VAELoader [3]      -> VAEEncode [12], VAEDecode [14], both TextEncode nodes
KSampler [13] -> VAEDecode [14] -> SaveImage [15]
```

Node/model/parameter values are identical to the audit's own
`build_qwen_edit_test.py` (Test B/D) plus the analyzer node from Test C —
no new node classes, no new model paths, nothing invented. All confirmed
live via `/object_info` on 2026-08-01 (current idle: 1133 MiB used /
14845 MiB free of 16303 MiB, queue empty).

Test images reused unchanged from Test B/C/D (already in `ComfyUI\input\`,
not recreated): `imgdir_test_source.png` (768x768, solid RGB 180/140/120,
tan), `imgdir_test_ref2.png` (768x768, solid RGB 60/60/180, blue),
`imgdir_test_ref3.png` (768x768, solid RGB 60/180/90, green) — three
visually distinct flat colors, satisfying "clearly distinguishable" without
introducing a new variable into the VRAM measurement.

## Measurement method

- `nvidia-smi --query-gpu=timestamp,memory.used,memory.free --format=csv,noheader -lms 250`
  run in the background, started 5-10s *before* submit and kept running
  10-20s *after* completion (not just submit-to-completion) — ~4x higher
  sampling rate than the audit's original ~1 Hz polling, to reduce the
  chance of missing a short sub-second peak, and wide enough to see a
  genuine flat baseline on both sides, not just the first/last sample.
- **Per-run gate, checked before every submit (E2 and, separately, E3):**
  `GET /queue` shows `queue_running`/`queue_pending` both empty, and the
  VRAM log shows a flat reading for at least ~5 consecutive samples
  immediately before submit. Do not submit E3 back-to-back off of E2's own
  post-completion resident state.
- **Node-cache bust for the analyzer:** the analyzer node's `seed` input
  is set to a distinct value per run (`build_graph.py`'s `analyzer_seed`
  argument), not left at the node's own default. Reason: ComfyUI caches a
  node's output across separate `/prompt` submissions on the same running
  server when its inputs are unchanged — Test C already ran the analyzer
  once on the same image with default settings on this same server
  process (PID 33352, still running), so without a forced input change the
  analyzer node could be silently cache-skipped in E2/E3, meaning no fresh
  VRAM allocation would occur and the very thing this test measures
  (analyzer alloc -> release -> editor alloc, under tighter headroom)
  would not actually happen. This does not change what is being measured;
  it only guarantees the analyzer actually executes. (Raised independently
  by Codex during plan review — see thread `019fbec8-4345-7af1-ba75-b996e16d801f`.)
- Graph submitted via `POST /prompt`, tracked via `GET /history/<prompt_id>`
  (`submit_and_monitor.py`) until `status.completed` is true or a node
  error appears. The helper also resolves each `SaveImage` output's actual
  file path under `E:\AI_Art\` and reports its on-disk size — a non-zero
  exit or "completed" status alone is not treated as sufficient evidence
  of criterion 6.
- `user\comfyui.log` (the live server's own log file) read before and
  after each run, read-only, to check for exceptions/OOM traces ComfyUI
  itself would emit — this is the log-excerpt artifact, not console
  scraping. (Note: `user\comfyui_8188.log` looks like the port-matching
  candidate but was found to be stale/unwritten since June 29 for this
  server process during E2 — `comfyui.log` is the one actually live.)
- Idle sample taken immediately before submit and after the VRAM series
  returns to a flat baseline post-completion.

## Acceptance criteria (from the user's instructions, restated for this plan)

E2 (and, separately, E3) passes only if all of:

1. graph completes with no ComfyUI/node error in `/history` status,
2. no CUDA OOM (surfaced as a node error / server log exception),
3. no server disconnect during the run (HTTP calls keep succeeding),
4. the VRAM series shows the analyzer's peak and the editor's peak as two
   distinct, non-overlapping plateaus, not a summed simultaneous peak,
5. between those two plateaus, the series shows a visible trough that
   drops back toward the pre-submit idle baseline (within a few hundred
   MiB of it), not just "looks lower than the two peaks" — the same shape
   Test C already showed for 1 reference image (idle 1537 -> peak 7855 ->
   back to 1537 -> editor ramp),
6. `SaveImage`'s output file exists on disk under `E:\AI_Art\` with a
   non-trivial size, confirmed via `submit_and_monitor.py`'s filesystem
   check (not inferred from HTTP status alone), no content/quality
   judgement,
7. sampled peak leaves >= 300 MiB free of 16303 MiB,
8. the actual number of `LoadImage` reference nodes wired into the editor
   matches the intended n_images (2 for E2, 3 for E3) — checked directly
   in the submitted graph JSON's `image1`/`image2`/`image3` slots on both
   `TextEncodeQwenImageEditPlus` nodes, not inferred.

E3 additionally requires: E2 passed all eight criteria above, AND a fresh
per-run gate (queue empty, flat VRAM baseline) is confirmed immediately
before E3's submit rather than reusing E2's tail state.

## Claude's own risk assessment (pre-Codex)

- **Biggest known risk, already flagged in the audit itself (§12/§13):**
  headroom at the editor's peak was already tight for 2-3 references without
  an analyzer in the same graph (D2: 516 MiB free sampled, D3: 809 MiB).
  Test C only combined the analyzer with a *1*-reference editor pass. E2/E3
  are the first time the analyzer's own execution (which, per Test C, fully
  releases before the editor loads) is combined with the tighter D2/D3-style
  headroom. If the analyzer's cleanup is even slightly incomplete this time
  (e.g. some fragmentation left over, or a slower release), the editor could
  push past 16303 MiB where Test C alone did not.
- **Sampling-rate limitation stays real:** 250 ms sampling is faster than
  the audit's original ~1 Hz, but still cannot prove no sub-250ms spike
  occurred. A completed run with headroom to spare is evidence the
  measured path is safe, not proof no shorter spike ever exceeds it.
- **Node "16" analyzer output is used as a live link into `prompt`, not a
  literal string.** This exact pattern is what Test C already validated
  end-to-end (audit §13), so it is not a new structural risk — flagging it
  only because it is the one part of the graph that is not a straight copy
  of the Test B/D script.
- **Missing evidence before running:** no one has checked whether
  `TextEncodeQwenImageEditPlus` costs meaningfully more VRAM per additional
  reference image *while the analyzer's own allocation is still settling
  down* (i.e. a timing interaction, not just an additive one). This plan
  cannot resolve that without running it — hence proposing E2 first, E3
  gated on a clean E2 pass, per the user's own instructions.
- **Smallest useful test:** exactly what the user specified — E2 alone
  first, real acceptance gate before E3, no combined "just run E3 directly"
  shortcut, since D2 already showed less headroom than D3 in isolation
  (allocator noise per §12, not a monotonic trend) and there's no reliable
  way to predict E3's margin from E2 alone.
