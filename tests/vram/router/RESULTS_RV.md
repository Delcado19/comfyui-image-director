# Router VRAM smoke test (RV-generate / RV-edit) — result

Closes the gap flagged in `tests/router/RESULTS_router_v1.md`/
`PROJECT_RULES.md`: "VRAM margins for the combined router graph have not
been measured the way E2/E3 measured the old analyzer+editor path." Reuses
E2/E3's exact methodology (`tests/vram/combined-multiref/TESTPLAN.md`)
applied to `tests/router/build_router_graph.py`'s actual router graph
(analyzer -> task extraction -> lazy switch -> selected branch ->
`SaveImage`) instead of a static non-router graph. Plan reviewed by Codex
(same thread as the rest of this project's joint decisions) before running -
two additions from that review are part of the method below: force `POST
/free {"unload_models": true, "free_memory": true}` before each run
(model-output-node caching is independent of GPU residency - a cached
loader node does not guarantee a model is still resident, but a
long-running server also should not be trusted to be at a genuine cold
floor without forcing it), and record the pre-submit baseline explicitly.

**Both runs PASS the adapted E2/E3 criteria - n=1 per direction**, same
scope as the rest of this milestone: a scheduling/VRAM characterization
pass, not a reliability screen.

## Method

- `POST /free` before each run, then 5 samples over ~5s confirming a flat
  floor before submitting - not just an HTTP 200 taken on faith.
- `nvidia-smi --query-gpu=timestamp,memory.used,memory.free --format=csv,noheader -lms 250`
  running in the background from before submit until well after
  completion (120-150s window, same ~4x-oversampled rate as E2/E3).
- Fresh `analyzer_seed` per run (cache-bust, same reason as E2/E3: force
  the analyzer to actually execute instead of a node-output cache hit).
- `tests/router/submit_and_check.py` (hardened per the earlier Codex
  review - raises on `node_errors`, incomplete status, log `[ERROR]`
  lines, or missing image output) used for submission/completion
  confirmation and the branch-identity check (`log_load_lines`).
- Output images visually inspected via the `Read` tool, not inferred from
  file presence alone.
- GPU: 16303 MiB total (same card as all prior VRAM tests in this project).

## RV-generate (task=generate, selects Z-Image Turbo)

Instruction: "Create a photorealistic product photo of a matte black
ceramic mug on a walnut desk in morning window light." Graph:
`tests/router/runs/RV_generate.graph.json` (analyzer_seed 81202).

- Pre-submit baseline: ~1263-1365 MiB used / ~14650-14715 MiB free, flat
  for 5+ samples before submit.
- prompt_id `2431d680-c1ec-4e31-a374-997e7caa81c1`, wall time 58.34s (n.b.
  slower than the earlier non-`/free`d runs - `/free` forced a genuine
  cold reload of the analyzer's own weights too, not just the router
  branches), `status.completed: true`, `log_errors: []`,
  `execution_cached.nodes: []` (confirms this was a genuine fresh
  execution, not a node-output cache hit for any node).
- `log_load_lines`: only `ZImageTEModel_`/`Lumina2`/`AutoencodingEngine`
  (Z-Image Turbo components) - no Qwen Image Edit components loaded.
- VRAM shape (473 samples over ~120s):
  - idle: ~1263-1365 MiB used (0-25s)
  - analyzer phase: peak ~7549 MiB used (25-33s)
  - **trough** (analyzer released): ~1327-1345 MiB used (35-43s) -
    genuinely back near the idle baseline, confirming clean
    `keep_model_loaded=false` release before the branch loads, same shape
    as Test C/E2/E3's analyzer-then-editor pattern
  - generate-branch ramp: climbs 43-52s
  - **peak: 13587 MiB used / 2391 MiB free** at 18:39:52.010 - a single
    ~250ms sample, immediately preceded and followed by ~10800-12400 MiB
    used readings, i.e. one brief spike (likely `VAEDecode`'s own
    allocation) rather than a sustained plateau
  - post-completion: settles to ~10800-10880 MiB used / ~5100-5175 MiB
    free and **stays there** - Z-Image Turbo's UNet/CLIP/VAE remain
    GPU-resident after the run (no automatic unload for this branch,
    unlike the analyzer's explicit `keep_model_loaded=false`)
- Output `ImageDirector_router_00004_.png`, visually inspected: a
  photorealistic matte black mug on a wood-grained desk in window light,
  matches the instruction.
- **Margin**: 2391 MiB free at the single worst sampled instant - well
  above the 300 MiB threshold used throughout this project's VRAM tests.

## RV-edit (task=edit, selects Qwen Image Edit 2511)

Instruction: "Remove only the blue square from the attached image. Keep
the red circle, background, and composition unchanged." Graph:
`tests/router/runs/RV_edit.graph.json` (analyzer_seed 81204). Fresh
`/free` + idle-floor confirmation run again before this submit - RV-edit's
baseline is NOT RV-generate's tail state (RV-generate left ~10850 MiB
resident; a second `/free` brought it back to ~1270-1285 MiB before this
run, same floor as RV-generate's own baseline).

- Pre-submit baseline: ~1279-1285 MiB used / ~14693-14699 MiB free, flat
  for 5+ samples before submit.
- prompt_id `3446cf6c-caf6-47df-8fcb-0cbbebbed1f0`, wall time 95.69s
  (slower again - cold analyzer reload plus Qwen Image Edit 2511's larger
  UNet), `status.completed: true`, `log_errors: []`,
  `execution_cached.nodes: []` (again a genuine fresh execution).
- `log_load_lines`: `WanVAE` (this install's VAE dtype-check message, not
  branch-specific - see `RESULTS_router_v1.md`), `QwenImageTEModel_`,
  `QwenImage` (edit-branch components) - no `ZImageTEModel_`/`Lumina2`
  (generate-branch) lines anywhere.
- VRAM shape (590 samples over ~150s):
  - idle: ~1279-1285 MiB used (0-14s)
  - analyzer phase: peak ~8257 MiB used (~14-19s)
  - **trough** (analyzer released): ~1299 MiB used (~20-22s) - again
    genuinely back near idle before the branch loads
  - edit-branch ramp: climbs steadily from ~22s to ~68s (`UnetLoaderGGUF`
    + `CLIPLoaderGGUF` + `VAELoader` load, `FluxKontextImageScale` +
    `VAEEncode`, then `KSampler`'s 8 steps holding the UNet, latents and
    both positive/negative conditionings resident simultaneously for the
    whole sampling duration - structurally different from Z-Image Turbo's
    brief-decode-spike shape, and visible in the data as a sustained
    plateau rather than a single spike)
  - **sustained tight plateau: 149 samples (~37.25s) with < 1200 MiB
    free**, worst single sample **954 MiB free / 15024 MiB used** at
    18:43:37.072 - this is a real, multi-second-long tight window, not a
    momentary spike like RV-generate's
  - post-completion: settles to ~10207-10270 MiB used / ~5709-5771 MiB
    free and stays there (same "stays resident" pattern as RV-generate)
- Output `ImageDirector_router_00005_.png`, visually inspected: blue
  square removed, red circle and background unchanged, matches the
  instruction exactly.
- **Margin**: 954 MiB free at the sustained worst point - still above the
  300 MiB threshold, but notably tighter than RV-generate's margin, and
  tighter than E2/E3's own *2-3 reference, fixed-bug* margins (1192 MiB
  free for 2 refs, 1303 MiB free for 3 refs) despite this being only
  *1* reference image here. Per Codex review: this is most likely due to
  the current Qwen Image Edit 2511 + abliterated Qwen2.5-VL-7B encoder
  combination having a larger combined footprint than E2/E3's older 2509 +
  standard-encoder pair (`PROJECT_RULES.md` already flagged those older
  numbers as unmeasured with the new file sizes, and this test is that
  re-measurement) - but the exact contributor is not isolated (e.g. not
  separately confirmed whether it's the UNet size, the encoder size, or
  something else). `/free` does not explain the gap: E2/E3's own "fixed
  cold" reruns also used `POST /free` as their preflight, so that is not a
  methodological difference between this test and those.

## Wording, per Codex's explicit caution during plan review

250ms sampling cannot prove no shorter spike ever occurs - "no sampled
overlap between the analyzer and branch phases, selected branch only per
log evidence, worst *sampled* margin X" is the accurate claim, not "proven
no overlap" or "proven safe at all times."

## Codex review (same thread as the rest of this project's joint decisions)

No blocker. This closes the specific flagged gap: the router graph's VRAM
behavior is now measured both directions with the actual graph, a genuine
fresh execution, a forced cold floor, selected-branch-only log evidence,
on-disk output files, and visual output checks. Explicit flag: RV-edit's
954 MiB free is a pass for the current single-source-image V1 router, but
it is "now the real binding constraint" - documentation must not imply
multi-reference edit routing is safe from this result; future `image2`/
`image3` router support needs its own dedicated VRAM pass before being
called safe. Ready to fold into `PROJECT_RULES.md`/`AGENTS.md` as done,
with the caveats kept explicit (n=1 per direction, 250ms-sampled margin
not proof against sub-250ms spikes, single-source-image scope only, the
954 MiB sustained margin, multi-reference needing its own re-test, and
back-to-back production usage without `/free` being uncharacterized since
branches stay resident).

## What this settles

- Both router directions show the same two-plateau-with-trough shape
  established for the non-router combined path (Test C/E2/E3): analyzer
  loads, peaks, and is fully released *before* the selected branch begins
  loading - no sampled overlap in either direction, confirming the lazy
  switch's boolean (itself derived from the analyzer's own output) does
  enforce sequential execution in practice, not just as a design
  expectation. This was the specific thing flagged as "not yet
  independently VRAM/timestamp-verified" in `RESULTS_router_v1.md` - now
  verified for the single-reference case.
- Both directions pass with real margin at the current single-source-image
  scope (2391 MiB / 954 MiB free at the respective worst sampled points,
  both well above the 300 MiB threshold), using the *current* (2511 +
  abliterated) model files - not the pre-swap numbers.
- Neither branch's loaded models are released after the run completes
  (both settle to a resident plateau, not back to idle) - relevant for
  planning any future "run generate then edit back-to-back without a
  `/free` in between" scenario, since the two branches' resident
  footprints would then coexist rather than one replacing the other.

## What this does not settle

- n=1 per direction, same as the rest of this milestone - not a
  reliability screen, and 250ms sampling cannot rule out a shorter,
  unsampled spike.
- Multi-reference (`image2`/`image3`) routing is still not implemented at
  the router level (see `RESULTS_router_v1.md`) - RV-edit's already-tight
  single-reference margin (954 MiB free, tighter than E2/E3's old
  *multi*-reference numbers) is a concrete reason to treat future
  multi-reference router support as needing its own dedicated VRAM
  re-test before being called safe, not an extrapolation from this result.
- The "both branches stay resident after completion" finding is new
  information, not previously documented for either branch in isolation -
  its implications for a production workflow that runs many requests
  back-to-back (memory fragmentation over time, whether ComfyUI's own LRU
  eviction handles branch-switching cleanly under repeated real usage) are
  not evaluated here.
- No image-quality, identity, or edit-locality claim is made beyond "the
  output visually matched the instruction" (n=1 per direction, same
  standard as `RESULTS_router_v1.md`).
