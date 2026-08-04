# Multi-reference router support + VRAM pass — result

Closes the "availability-specific schema selection" gap flagged since the
router's first milestone (`PROJECT_RULES.md`): `tests/router/build_router_graph.py`
only ever supported a single source image. Extended `build()` to accept
`refs: list[str]` (0-2 entries), following the exact wiring pattern already
proven for the non-router path in `tests/vram/combined-multiref/build_graph.py`
(E2/E3): extra `LoadImage` nodes, added to the analyzer's `image2`/`image3`
inputs (contiguous-slot validated by `QwenVLStructuredGGUF` itself) and to
both `TextEncodeQwenImageEditPlus` nodes (pos + neg) in the edit branch.
Schema `reference_count` is picked from `len(refs)` at graph-build time via
`image_director.edit_plan_schema.edit_plan_schema(source_image=True,
reference_count=N)`, which already supported N=0/1/2. `GUIDANCE`'s prompt
text now tells the analyzer how many images it's looking at (previously
silent on this, since the router was single-image-only).

Backward compatible: `refs=None`/`[]` (the CLI default when no extra
filenames are given) produces byte-identical graph shape to before this
change - verified by inspecting the built graph (`analyzer` inputs only
have `image`, no `image2`/`image3`; `edit_cond_pos`/`edit_cond_neg` inputs
unchanged).

## Correctness (before VRAM measurement)

Ran a 3-image (source + 2 references) request through the live router
first, unrelated to VRAM, to confirm the wiring actually works:
prompt_id `f4206eec-8f82-4083-8770-96352be22756`, completed, no errors.
Log confirms only edit-branch components loaded (`WanVAE`,
`QwenImageTEModel_`, `QwenImage`) - no `ZImageTEModel_`/`Lumina2` lines,
same lazy-switch guarantee as the single-image case holds with references
present. Output `ImageDirector_router_00013_.png` produced.

## VRAM pass method

Same cold-floor methodology as `RESULTS_RV.md`: fresh `POST /free`,
confirmed idle floor, one continuous `nvidia-smi` CSV log (250ms) per run,
fresh seeds each time. Two runs:

- **RVref2** (source + 1 reference, `imgdir_test_ref2.png`):
  `tests/router/runs/RVref2_edit.graph.json`, log `vram_log_RVref2.csv`.
- **RVref3** (source + 2 references, `imgdir_test_ref2.png` +
  `imgdir_test_ref3.png`): `tests/router/runs/RVref3_vram.graph.json`, log
  `vram_log_RVref3.csv`.

## Result

- **RVref2: worst sampled margin 532 MiB free.** prompt_id
  `815bf8bc-b231-4702-abbf-5535cf1ea839`, completed, no errors, output
  `ImageDirector_router_00014_.png`.
- **RVref3: worst sampled margin 916 MiB free.** prompt_id
  `4247bfde-9187-40b6-8bb1-52ac18f2e959`, completed, no errors, output
  `ImageDirector_router_00015_.png`.
- Both log-confirmed `full load: True` for the edit branch's `QwenImage`
  UNet, no OOM, no lowvram fallback.

Neither result is below this project's 300 MiB floor - both pass. RVref3
(more images) showed *more* headroom than RVref2 in this n=1 pair, not
less - counter to a naive "more images = more VRAM = tighter margin"
expectation. Given `RESULTS_RVfix.md`'s isolated single-image edit case
(456 MiB) and this session's documented run-to-run drift (see that file's
"unexplained ~500 MiB gap" note), these numbers should be read as "passed
with some margin, magnitude noisy," not as a precise linear relationship
between reference count and VRAM pressure.

## What this settles

- The router now supports 0, 1, or 2 reference images - the "availability-
  specific schema selection" gap is closed.
- Both tested reference counts pass this project's 300 MiB VRAM floor from
  a clean cold start.
- Lazy-switch correctness (unused branch never loads) holds with
  references present, not just in the single-image case.

## What this does not settle / open concern

- n=1 per reference count - not a repeated-use or back-to-back-without-
  `/free` measurement. Given `RESULTS_RVfix.md`'s finding that the plain
  single-image edit case gets meaningfully tighter under back-to-back
  sequencing (456 -> 238-271 MiB), the same is plausible but unmeasured
  for the multi-reference case - do not assume these margins hold under
  repeated production usage without `/free`.
- Only tested with the edit task (references only make sense for editing
  in this schema design) - not tested with `task=generate` alongside
  reference images present but unused.
- Plan/content quality with real multi-reference semantics
  (`reference_slots` accuracy, whether the model actually uses the
  reference images correctly) not evaluated - this test only checks
  structural/VRAM correctness, same scope limitation as every other VRAM
  pass in this project.
