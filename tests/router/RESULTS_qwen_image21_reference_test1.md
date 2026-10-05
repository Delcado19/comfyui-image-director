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
  VRAM-mitigation gate needed either (not yet measured, but the model is
  far smaller: ~4GB UNET + ~6.3GB text encoder vs. Dev's 17.9GB UNET alone).

**This does not retroactively validate Klein/Dev's results or invalidate
them** - those remain correct for their own mechanisms. It also does not
yet prove Qwen-Image-2.1 is production-ready: n=1, one easy fixture, a
third-party "Native Test" community quant (not an official release), no
VRAM/timing characterization, no material/texture test, no second seed, no
numeric locality check (the Klein/Dev tests both eventually got one - this
hasn't yet).

## What this does and does not establish

**Established**: the native mechanism works and, on this first sample,
outperforms every masking-based approach this project built, at
dramatically lower engineering complexity.

**Not yet established**: reliability across seeds, material/texture
transfer (not just flat-color swatches), VRAM/timing margins, behavior on
harder content (the original case-3 motivation this whole investigation
traces back to - Klein was judged "not capable enough" for a SPECIFIC
harder scenario, not this easy fixture), whether this holds for the
eventual official (non-community-quant) release, and whether `resolution`/
prompt-wording choices made here are actually load-bearing or just happened
to work on the first try.

## Files

- `tests/router/qwen_image21_reference_test1.py` - the test script,
  includes the Autogrow wiring fix and its explanation in the module
  docstring for future reference.
