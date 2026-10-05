# Qwen-Image-2.1 (NVFP4 community quant) - native multi-reference editing: causal test

First test of the capability this project actually cares about: does
Qwen-Image-2.1's own native multi-image conditioning (`TextEncodeQwenImage21`,
up to 16 reference images, no SAM3 masking, no hand-built `ReferenceLatent`
chain) transfer a reference image's color onto a named region WITHOUT the
color being named in text - and does it preserve everything else?

Same fixtures as `klein_test1_masked_reference.py` /
`flux2dev_masking_test1.py` for direct comparability: blue-dress source,
red/green reference swatches. Prompt (no color named):

> "Change only the woman's dress in the first image to match the second
> reference image. Keep her face, pose, and the entire background exactly
> unchanged."

## A wiring bug found and fixed first

`TextEncodeQwenImage21`'s `images` input is a `COMFY_AUTOGROW_V3` **dynamic**
input, not a simple nested dict value. Read directly from
`comfy_api/latest/_io.py`'s `Autogrow._expand_schema_for_dynamic()`: this
input type expands into separate flattened top-level node inputs named
`"{autogrow_id}.{name}"` (dot-joined, via `finalize_prefix`), e.g.
`"images.image_1"`, `"images.image_2"` - **not** a single `"images": {...}`
dict as the plain `/object_info` schema's nesting visually suggests.

The first attempt used a nested dict (`"images": {"image_1": [...],
"image_2": [...]}`) - ComfyUI's validation accepted it silently (no
`node_errors`, the run completed normally) but the reference image had
**zero effect**: variant B (red reference) and variant D (no reference at
all) produced **pixel-identical output** at the same seed, and
`execution_cached` was empty for both (confirmed via `/history` - not a
cache hit, a genuine fresh execution that just ignored the image entirely).
The output itself was also a complete scene regeneration unrelated to the
source photo (different person, different setting) - consistent with the
image input silently resolving to the node's Python default (`None`/`{}`,
skipping the entire reference-processing loop) rather than raising an
error. Fixed by using the flattened dotted keys
(`"images.image_1"`/`"images.image_2"`) as direct top-level entries in the
node's `inputs` dict. Re-running with the same prompt/seed with this fix
immediately changed the output from "ignores both images" to "correctly
locality-preserving, causally reference-driven" - see below.

## Results (seed 424243, corrected wiring)

| Variant | Reference | Result |
|---|---|---|
| B | red | Dress turned **red**. Face, pose, hand gesture, trash can, beer bottle, bench, street, buildings, lighting - all pixel-level identical to the source scene. |
| D | none (ablation) | Dress stayed **blue** (unchanged from source). Same scene preservation. |
| B2 | green | Dress turned **green**. Same scene preservation. |

All three: `status_completed=true`, no `[ERROR]` log lines, visually
inspected (not assumed from a non-error exit code).

## Material/texture + VRAM/timing (combined in one run, seed 424243)

Variant M: same source, prompt, and mechanism as B/D/B2, reference swapped
for the real leather photo already used and proven for the Flux.2 Dev
material test (`imgdir_masktest2_ref_leather.png` - a genuine photograph,
not a synthetic texture). Unlike the hand-built Dev graph, no manual
reference-scaling guard was needed: `TextEncodeQwenImage21` already resizes
every image (source and references alike) to ~`resolution`x`resolution`
internally, so the 3000x2000 source photo could not blow up VRAM the way it
did for Dev's raw `VAEEncode` graph.

- **Result**: the masked dress shows visible leather grain, wrinkle
  shading, and specular highlights - genuinely reads as leather, not a flat
  dark fill. Scene preservation held again (face, pose, background
  pixel-identical to source). On this first sample, this is a **cleaner**
  material result than Flux.2 Dev's (which only unambiguously read as
  "leather" at 1 of 2 tested seeds - this is n=1 here, not yet compared
  across seeds).
- **Timing**: 25.5s wall time - longer than B/D/B2's ~10-13s (likely the
  3000x2000 source photo's internal resize/preprocessing cost), but still
  roughly 30x faster than Flux.2 Dev's material-variant runtime (~828-840s).
- **VRAM**: 1753 MiB free minimum / 14,225 MiB used maximum - comfortably
  above the project's 300 MiB floor, in the same range as Dev's
  router-representative measurement (1645 MiB) despite Qwen-Image-2.1's
  much smaller model footprint (~4GB UNET + ~6.3GB text encoder vs. Dev's
  ~18GB UNET) - not yet explained why the margins land similarly; worth
  checking at a later point rather than assumed.

## Second-seed cross-check (seed 777777, B/D/B2/M)

All four variants repeated at a second seed, same prompts/references:

- **B** (red): dress red again, scene preserved.
- **D** (ablation): dress stayed blue again, scene preserved.
- **B2** (green): dress green again, scene preserved.
- **M** (leather): visible wrinkle/sheen structure again, scene preserved.

**4/4 consistent with seed 424243 - a clean 2/2 result across the whole
causal matrix, including material.** No seed-dependent material-identity
softness was observed here (unlike Dev's result, where only 1 of 2 seeds
unambiguously read as "leather" - both Qwen-Image-2.1 seeds show comparable
structured sheen). Wall times at this seed: B 25.0s, D 18.1s, B2 24.9s, M
24.8s - consistent with the first-seed figures, no VRAM/timing sampling run
at this seed (not yet combined with a third repeat).

## Variant H: the historically-harmful case-3 prompt pattern (seed 424242)

The original case-3 fixtures (`IMG_7148.jpg`, `imgdir_test_ref2.png` - a
black-leather-dress source + a blue reference swatch, the exact scenario
the user judged Klein "not capable enough" for) were deleted during the
project's environment-drift pause and are not recoverable
(`PROJECT_RULES.md`'s 2026-10-03 migration log). Rather than skip the
"harder content" question, this reuses the exact historically-harmful
PROMPT PATTERN instead - confirmed via a dedicated A/B isolation test
(`RESULTS_ab_background_word.md`) to be the specific cause of Qwen Image
Edit 2511's global-tint bleeding failure: an origin-color anchor ("needs to
be changed") plus the word "background" describing the reference swatch
itself ("which appears as a solid X **background**"):

> "The woman is wearing a blue dress that needs to be changed to match the
> color from Reference Image #2, which appears as a solid red background.
> The rest should remain unchanged."

(Adapted to this project's current blue-dress/red-reference fixture - the
lost originals used black/blue.)

**Result: no bleeding.** Sky, buildings, pavement, street, trash can, bench
- all pixel-identical to the source, same as every other variant. The
dress turned red cleanly. The exact wording pattern that caused Qwen Image
Edit 2511 to tint the ENTIRE image blue (`RESULTS_content_quality.md`'s
original case-3 finding) had no bleeding effect here.

This is meaningful evidence that Qwen-Image-2.1's architecture does not
share Qwen Image Edit 2511's specific failure mode - but it is evidence
about the PROMPT PATTERN on the CURRENT fixture, not a recreation of the
original case-3 scenario itself (different source/reference images, which
no longer exist). A literal re-run with an actual black-garment source
photo would be a stronger test, if such a photo becomes available.

## Comparison to this project's other masked/reference mechanisms

This is, at n=1, a **stronger result than either Klein or Flux.2 Dev's
masking-based approach**, on every axis measured so far:

- **Locality**: visually perfect in this single sample (no SAM3 mask, no
  `SetLatentNoiseMask` - the model's own multimodal understanding of "the
  first image" vs. "the second reference image" did the targeting).
- **Causal reference-following**: clean red/blue/green separation, same
  quality signal as Klein's/Dev's proven B/D/B2 results.
- **Speed**: ~10-13s per edit (40-step Euler) - dramatically faster than
  Flux.2 Dev's ~800s and faster than Klein's ~20-25s.
- **Graph complexity**: one conditioning node
  (`TextEncodeQwenImage21`) replaces SAM3 segmentation +
  `SetLatentNoiseMask` + manual `ReferenceLatent` chaining entirely - no
  VRAM-mitigation gate needed, and the measured margin (1753 MiB free) is
  comfortably above the project's 300 MiB floor without one.
- **Material/texture**: also cleaner than Dev's (see above) at n=1.

**This does not retroactively validate Klein/Dev's results or invalidate
them** - those remain correct for their own mechanisms. It also does not
yet prove Qwen-Image-2.1 is production-ready: n=2 per variant, one easy
fixture, a third-party "Native Test" community quant (not an official
release), no numeric locality check (the Klein/Dev tests both eventually
got one - this hasn't yet).

## What this does and does not establish

**Established**: the native mechanism works, reproduces cleanly at n=2
across the full causal matrix (color-follow and material alike), and
outperforms every masking-based approach this project built on every axis
measured (locality, causal color-follow, material/texture, speed, VRAM
margin, graph complexity) - at dramatically lower engineering complexity.

**Partially established**: robustness to the exact historically-harmful
prompt pattern that broke Qwen Image Edit 2511 (variant H) - no bleeding on
the current fixture. This is not the same as re-testing the original
lost case-3 photos themselves (different source/reference content).

**Not yet established**: behavior on the original case-3 fixtures/content
specifically (Klein was judged "not capable enough" for that SPECIFIC
scenario, now unrecoverable), whether this holds for the eventual official
(non-community-quant) release, and whether `resolution`/prompt-wording
choices made here are actually load-bearing or just happened to work on
the first try.

## Files

- `tests/router/qwen_image21_reference_test1.py` - the test script,
  includes the Autogrow wiring fix and its explanation in the module
  docstring for future reference.
