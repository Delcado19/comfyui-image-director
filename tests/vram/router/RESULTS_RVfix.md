# Analyzer-eviction fix (Option C) — validation result

Validates the fix agreed in `RESULTS_RVchain.md`'s "what this does not
settle" section: `QwenVLStructuredGGUF` gets an opt-in
`free_vram_before_load: BOOLEAN` (default `False`). When `True` and the
node is about to load a genuinely new model (signature differs from what's
currently loaded), it calls `comfy.model_management.unload_all_models()` +
`soft_empty_cache()` immediately before `Llama(...)`. Set to `True` only in
the V1 router graph's analyzer node instantiation
(`tests/router/build_router_graph.py`); every other caller of the node
stays at the `False` default.

**Result: the fix closes the gap it targeted. It also surfaced a second,
separate near-miss margin - the edit branch's own diffusion load - that
was not visible before because the analyzer's squeeze was the tightest
point in the earlier test.**

## Method

Same back-to-back-without-`/free` method as `RESULTS_RVchain.md`: fresh
`/free`, RV-generate submitted and completed, then RV-edit submitted
immediately after with no `/free` between - now with
`free_vram_before_load=True` on the analyzer. Run twice (RVfix,
RVfix2) with fresh seeds each time to check whether the result was noise.
Graphs: `tests/router/runs/RVfix_generate.graph.json` /
`RVfix_edit.graph.json`, `RVfix2_generate.graph.json` / `RVfix2_edit.graph.json`.
CSV logs: `vram_log_RVfix.csv`, `vram_log_RVfix2.csv`.

## What the fix fixed

In both runs, VRAM used drops sharply right before the analyzer's
`Llama(...)` load - e.g. run 1: 11555 -> 2051 MiB used in a single ~250ms
sample at 08:00:21, confirmed against the log's mmproj/analyzer lines
starting immediately after. ComfyUI's own model manager has nothing
resident when the analyzer loads now, so the analyzer no longer stacks on
the previous branch's weights. The original 901 MiB near-miss location
(analyzer load stacking on resident diffusion weights) does not recur in
either run - the analyzer's load window in both runs stays well above the
project's 300 MiB floor.

## New finding: the edit branch's own diffusion load is now the tightest point

- Run 1 (RVfix): worst sampled margin **271 MiB free**, at 08:01:19-08:01:53,
  during Qwen Image Edit 2511's own load/`KSampler` phase. Log: `[INFO]
  loaded completely; 12994.09 MB usable, 12739.05 MB loaded, full load:
  True` for `QwenImage` at 08:01:14, immediately before the tight window.
- Run 2 (RVfix2): worst sampled margin **238 MiB free**, same phase, same
  `full load: True` confirmation in the log. Tighter than run 1, not
  looser - not a fluke in one direction.
- Both runs: no errors, no OOM, no lowvram/partial-load fallback (`full
  load: True` both times), both prompts completed, correct visual output
  (`ImageDirector_router_00009_.png`, `ImageDirector_router_00011_.png`).

n=2, both below the project's established 300 MiB safety floor, same
location both times - reproducible, not attributed to run-to-run noise.

## Codex review (thread `019fcb5f-8503-7641-85a0-f7a74b1b7659`, same
project joint-decision process, new thread since the prior one expired)

Confirmed the analyzer-load fix works as designed. On the new 238-271 MiB
finding: agreed it's reproducible at n=2, not noise, and should be
documented as a separate pressure point from the (now closed) analyzer
gap - but cautioned against claiming the analyzer's own eviction call is
*proven* unrelated to the edit branch's tighter footprint: "The exact
contributor is not isolated: QwenImage footprint, allocator state after
back-to-back generate/analyzer/free/load, fragmentation, or small residual
residency could all contribute. Regardless of contributor, the production
rule stays simple: no back-to-back router usage without `/free` until this
edit-branch margin has a mitigation or wider-margin repeated test."
Suggested (not yet run) isolation test: fresh `/free` -> RVfix-edit only
(no preceding generate request), repeated once, to separate "requires the
prior generate run" from "this is now just the edit branch's own steady
footprint regardless of what ran before it."

## What this settles

- The analyzer-load stacking gap identified in `RESULTS_RVchain.md` is
  fixed for callers that set `free_vram_before_load=True` (currently: the
  V1 router graph's analyzer node only).
- Back-to-back router usage without `/free` is *not* newly safe overall -
  the tightest point just moved from the analyzer's load to the edit
  branch's own diffusion load, and that point is measured tighter (n=2:
  271, 238 MiB free) than the original problem it replaced (901 MiB).

## What this does not settle / open concern

- n=2 on the *edit-branch* margin specifically - same caveat the original
  RVchain finding had: not a wide safety margin, and CUDA/driver-level
  variance could plausibly push a future run past 0 MiB free.
- Root cause of the edit branch's own tight margin not isolated (see
  Codex's caution above). Not established whether it depends on the
  preceding generate request, the preceding analyzer's eviction call, or
  is simply Qwen Image Edit 2511's own back-to-back footprint regardless
  of what ran before it.
- No fix proposed for this second finding - out of scope for this pass.
  See `PROJECT_RULES.md`'s mandatory safety rules for the resulting hard
  rule update.
