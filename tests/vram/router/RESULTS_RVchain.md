# Back-to-back router requests without `/free` — result

Closes the gap `RESULTS_RV.md` flagged as uncharacterized: both router
branches stay GPU-resident after completion, and a real production router
would presumably not call `POST /free` between every single request (that
would defeat some of the latency benefit of not reloading). This test
checks what actually happens if RV-generate's resident state is still
sitting in VRAM when RV-edit is submitted immediately after, with no
`/free` in between.

**Result: completed without error, but found a genuine near-miss margin -
tighter than any previously recorded pass in this project - caused by an
architectural gap Codex identified before the test ran.**

## Codex's pre-test finding (this is why the test was designed this way)

Before running, Codex reviewed the plan and pointed out the risk is not
where it first looks. `QwenVLStructuredGGUF` (the analyzer node, external
repo `comfyui-qwenvl-structured-gguf`) loads its GGUF model directly via
`llama_cpp.Llama(...)` (`nodes/structured_gguf_vl.py:78-102`) - this call
allocates GPU memory through llama.cpp's own CUDA backend, completely
outside ComfyUI's `comfy.model_management` system. It does not call
`free_memory()` or request eviction of any kind before allocating. Since
the analyzer runs *first* on every single request regardless of which
branch gets routed to, the actual first pressure point in a no-`/free`
back-to-back sequence is "resident branch models + a new analyzer load,"
not "resident branch models + the next branch's own loaders" - and
ComfyUI's own eviction logic can only react to allocation requests it
knows about (its own loader nodes), not the analyzer's raw llama.cpp call.
This is exactly what the data below confirms.

## Method

Continuation of `RESULTS_RV.md`'s method, but deliberately breaking one
rule: `POST /free` called only once, before RV-generate (giving it its own
clean baseline measurement); **no `/free` before RV-edit** - it is
submitted immediately after RV-generate completes, with RV-generate's
~10867 MiB resident state still in place. One continuous `nvidia-smi` CSV
log (250ms) spans both submissions. Fresh `analyzer_seed`/sampler seed on
both graphs (`tests/router/runs/RVchain_generate.graph.json`,
`RVchain_edit.graph.json`). Per Codex's guardrails: expected (not treated
as a failure) that the second run's `execution_cached.nodes` list is
non-empty for the *generate* branch's static loader nodes (`gen_unet`,
`gen_clip`, `gen_vae`, `gen_model`, `gen_latent`, `src`) - those are simply
unrelated to what's being routed to this time, and a node-output cache hit
on them is expected, not evidence of a problem. `POST /free` called again
after the whole test, regardless of outcome, to leave the server clean.

## Timeline

- Idle baseline (fresh `/free`): ~1327-1417 MiB used.
- RV-generate: analyzer peak ~8352 MiB used -> trough ~1371-1401 (clean
  release) -> Z-Image Turbo ramp -> peak ~12427 used -> **settles at
  10867 MiB used / 5111 MiB free and holds flat** (18:59:10-19:00:33,
  confirmed flat for the last ~10s/40 samples before the next submit).
  prompt_id `212f5a10-de91-450f-aff7-da7a9532694c`, wall time 50.03s,
  completed, no errors, `log_load_lines` confirm Z-Image Turbo only.
  Output `ImageDirector_router_00006_.png` visually correct.
- **RV-edit submitted at 19:00:36 with no `/free`, resident baseline still
  10867/5111.** Within ~250ms (sample 336, 19:00:36.284): used jumps to
  13020 (free 2958). Next sample (337, 19:00:36.539): **used 15077 / free
  901 MiB - the global minimum of this entire run**, held for ~750ms-1s
  (samples 337-340), then fluctuates in the 900-1500 MiB-free range for a
  further ~5-6 seconds (samples 341-359, 19:00:37.556-19:00:42.161) - this
  whole window is the analyzer's own GGUF load happening on top of the
  still-fully-resident Z-Image Turbo models, unmanaged by ComfyUI.
- **Eviction event at sample 360 (19:00:42.413): used drops sharply from
  14465 to 7507 MiB (a ~6958 MiB drop) in a single 250ms sample.** This
  lines up almost exactly with the log's `[INFO] Requested to load WanVAE`
  line at 19:00:43.184 - i.e. eviction happened right when the edit
  branch's *own* `VAELoader` (a ComfyUI-managed node) requested memory
  through `comfy.model_management`, which *does* evict stale resident
  models to make room. Before that moment, nothing evicted the old
  Z-Image Turbo weights, because nothing ComfyUI-managed had asked for
  memory yet - the analyzer's raw llama.cpp allocation doesn't trigger it.
- Edit branch continues loading/ramping from the freshly-evicted state,
  reaching a second sustained tight window later during `KSampler`'s own
  run: 150 samples (~37.5s, 19:01:06.742-19:01:44.665) with < 1600 MiB
  free, worst single sample **1198 MiB free** (19:01:42.378) - comparable
  in kind to `RESULTS_RV.md`'s clean RV-edit sampling-phase plateau (954
  MiB free there), slightly more comfortable here because the eviction at
  sample 360 freed more headroom at once than a from-idle cold start
  needed.
- prompt_id `f1a49d16-d89d-470b-a4f9-c325a3ad5acc`, wall time 71.22s,
  completed, no errors. `log_load_lines`: only `WanVAE`/`QwenImageTEModel_`/
  `QwenImage` (edit-branch components) - no `ZImageTEModel_`/`Lumina2`
  lines, confirming correct branch identity despite the stacked start.
  Output `ImageDirector_router_00007_.png` visually correct (blue square
  removed, red circle and background unchanged).

## The finding

**Worst sampled margin of this entire back-to-back run: 901 MiB free**,
occurring during the *analyzer's* load while the previous request's
diffusion branch was still fully GPU-resident - not during either
diffusion branch's own sampling. This is the tightest margin recorded in
this project's history (tighter than `RESULTS_RV.md`'s own 954 MiB
edit-branch record from a clean cold floor), sustained across multiple
consecutive 250ms samples (not a single-sample blip), and it remained safe
only until ComfyUI-managed eviction occurred a few seconds later, once a
ComfyUI-managed node (not the analyzer) made its own allocation request -
not because anything proactively made room for the analyzer's load.

This did not fail this time. But it is a real, evidence-based concern for
any production usage pattern that skips `/free` between requests to save
latency: the analyzer's own load is not currently protected by ComfyUI's
eviction logic at all, and a request sequence that stacks a
slightly-larger resident model, a slightly larger analyzer context, or
simply unlucky timing with OS/driver overhead could plausibly push this
past 0 MiB free and into a real CUDA OOM - something this project's
existing 300 MiB threshold was not calibrated against a case this tight.

## Codex review (same thread as the rest of this project's joint decisions)

Confirmed the characterization as accurate and recommended treating this
as a hard project rule, not just a documented open concern: "this is not
just an 'open concern' anymore. The test identified a specific
architectural gap, reproduced the predicted pressure point, and passed
with only 901 MiB sampled free while the analyzer loaded outside
ComfyUI's model manager. That is above the old 300 MiB floor, but the old
floor assumed managed/sampled diffusion workflows, not an unmanaged
llama.cpp allocation stacked on resident branch weights." No further live
run needed before documenting; a reverse-order test (edit-branch resident,
then generate) could be run later but "would not remove this finding."
See `PROJECT_RULES.md`'s mandatory safety rules for the resulting hard
rule.

## What this settles

- Back-to-back router requests without `/free` complete successfully at
  n=1, both branch identities remained correct, both outputs remained
  visually correct.
- The actual risk in a no-`/free` production sequence is the *analyzer's*
  load stacking on top of a resident previous branch, not the next
  branch's own diffusion pipeline - ComfyUI's own model manager already
  handles eviction correctly for its own managed loaders once they
  request memory, but has no visibility into (and cannot pre-evict for)
  `QwenVLStructuredGGUF`'s direct llama.cpp allocation.

## What this does not settle / open concern

- n=1 - this passed by a margin of 901 MiB, not by a wide safety margin;
  a repeat run, a different prompt/context length, or minor system-level
  VRAM variance could plausibly not pass. This should not be treated as
  "back-to-back usage is safe."
- No fix has been proposed or implemented. Two directions worth the
  user's/Codex's input before this is used in any real repeated-request
  scenario: (a) have the router graph (or the analyzer node itself) call
  ComfyUI's `/free`-equivalent (`comfy.model_management.free_memory()` or
  `unload_all_models()`) before the analyzer's own `Llama(...)` load, so
  eviction happens proactively instead of by accident a few seconds later;
  or (b) accept the `/free`-between-every-request latency cost as the
  operational policy until/unless (a) is built. This test does not choose
  between those - it only establishes that the current unmodified state
  has this specific, evidence-based gap.
- Reverse order (edit-branch resident, then generate-branch/analyzer on
  top) not tested - RV-edit's own resident footprint (~10207-10270 MiB
  used) is slightly smaller than RV-generate's (~10850-10890 MiB), so the
  analyzer-under-load squeeze in that direction is plausibly *less* tight,
  but this has not been measured, only reasoned about.
