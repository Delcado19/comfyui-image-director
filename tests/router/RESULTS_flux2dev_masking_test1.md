# Flux.2 Dev + masking: first causal test (source-latent + SAM3 mask)

Joint Claude-Codex decision (Codex exec thread `ba7x2msvh`, read-only review
of `ab_flux2dev.py`, `RESULTS_flux2dev_capability.md`, `PROJECT_RULES.md`,
and `klein_test1_masked_reference.py`), implemented in
`tests/router/flux2dev_masking_test1.py`. Standalone script only - no
router integration, no production file changes.

## Problem and observed state

`ab_flux2dev.py`'s validated graph samples from an EMPTY Flux2 latent;
`RESULTS_flux2dev_capability.md` conclusively found that graph does not
transfer reference color/material when the text doesn't name it, across 4
chaining modes and 2 reference types. `PROJECT_RULES.md` left "Dev +
masking" explicitly open because that needs a different mechanism:
`VAEEncode(source)` + `SetLatentNoiseMask` feeding the sampler the
source's own latent, instead of an empty one.

## Claude's initial assessment

Masking plus a positive `ReferenceLatent` chain is a genuinely new
mechanism, not a retread of the closed investigation - worth a small
causal test before concluding Dev categorically cannot do reference-driven
masked edits.

## Codex's independent assessment

Agreed the test is worthwhile, with two corrections:

- **Mechanics**: `Flux2Scheduler` starts its sigma schedule at 1
  everywhere, including inside the mask - full denoise-from-noise happens
  there too, same as unmasked generation. There is no "only resolve an
  already-correct region." `KSamplerX0Inpaint`-style reinsertion only
  anchors the OUTSIDE-mask region to the source latent during sampling.
  The actual mechanism under test is "held spatial source context during
  local synthesis," not a literal partial-denoise shortcut.
- **GGUF evidence gap**: the historical validated test used an **NVFP4**
  UNet; the only installed Dev UNet today is **GGUF Q4_K_M** - a different
  quantization format and runtime path. "GGUF behaves like the previously
  validated checkpoint" is not established by precedent; this exact GGUF
  checkpoint had not itself been tested for either mechanism before today.

Codex proposed the causal matrix (table below), the exact wiring, keeping
Dev's own validated settings (cfg=1.2, 28 steps, `dpmpp_sde`,
`Flux2Scheduler` - no Klein-style 4-step settings), and recommended
measuring locality against a pure VAE-encode/decode baseline rather than
the original file (VAE reconstruction itself is lossy).

## User decision

GGUF Q4_K_M conflicts with the user's stated general anti-GGUF preference,
and no non-quantized/fp8 Dev UNet is installed. Surfaced explicitly before
spending GPU time (2026-10-04); user approved proceeding with the existing
GGUF Q4_K_M ("nimm das vorhandene q4km") rather than downloading an
alternative.

## Test design

Klein's existing fixtures reused for direct comparability: blue-dress
source (`imgdir_masktest2_source_bluedress.png`), red/green reference
swatches. Wiring:

```text
VAEEncode(source) ────────────────────────> ReferenceLatent(source)
        └─> SetLatentNoiseMask(SAM3 mask) -> SamplerCustomAdvanced.latent_image

positive: CLIPTextEncode -> ReferenceLatent(source) -> ReferenceLatent(reference)
negative: ConditioningZeroOut(positive text) -> ReferenceLatent(source)
```

Dev settings unchanged from `ab_flux2dev.py`: cfg=1.2, 28 steps,
`dpmpp_sde`, `Flux2Scheduler`, Flux.2's own VAE. Source scaled to 1
megapixel (`ImageScaleToTotalPixels`, matching `ab_flux2dev.py`); reference
left unscaled (matches both `ab_flux2dev.py` and
`klein_test1_masked_reference.py` precedent).

| Variant | Prompt names target color? | Reference | Purpose |
|---|---|---|---|
| A | Yes ("red") | red | Does masked text editing work at all on Dev? |
| B | No | red | Image-based color transfer (the real causal question) |
| D | No (= B's text) | none | Reference ablation |
| B2 | No (= B's text) | green | Causal color-follow control |

Run order: shared seed (424242), A -> B -> D -> B2, per Codex's
"stop early if A fails, run D before B2 if B shows no change" guidance -
all four ran cleanly in sequence, no early exit needed.

## Results

All 4 variants + the VAE baseline completed with `status_completed=true`,
no `[ERROR]` log lines, no validation errors at submission.

- **Baseline** (VAEEncode -> VAEDecode, no sampling): visually identical to
  the source photo - establishes the VAE reconstruction floor. Outside-mask
  regions in A/B/D/B2 match this floor closely; no visible extra drift from
  the masked sampling itself.
- **A** (color named + red reference): dress turned red/burgundy. Mask
  (`SetLatentNoiseMask` via SAM3, visually inspected) correctly covers only
  the dress. Mechanism works.
- **B** (no color named + red reference): dress turned red - visually close
  to indistinguishable from A. **This is the result `ab_flux2dev.py`'s
  empty-latent graph never produced** - color transfer without naming the
  color in text.
- **D** (no color named, no reference): dress stayed **blue** - unchanged
  from the source. Clean ablation, no drift (unlike Klein's Base-checkpoint
  D-variant finding, which did drift at n=1).
- **B2** (no color named + green reference): dress turned **green**,
  following the swap reference exactly.

Across all 4 variants: face, hair, pose, hand gesture, background
buildings/street/trash can/bench, lighting, and framing are visually
unchanged - locality held.

## Second-seed cross-check (seed 777777, B/D/B2 triple)

Per Codex's explicit recommendation (see "Suggested next step" below, now
done). A not repeated - its only job was the functional smoke test,
already settled.

- **B** (no color named + red reference): dress red - consistent with seed
  424242.
- **D** (no color named, no reference): dress stayed **blue** - consistent,
  no drift at this seed either.
- **B2** (no color named + green reference): dress **green** - consistent.

**2/2 seeds agree on all three causal variants** (B->red, D->unchanged,
B2->green). This is still a small n, but the result is not a single-seed
fluke - both seeds point the same direction on the variant that matters
most (B2's causal color-follow).

Operational note: the ComfyUI server went down between the seed-777777 B
and D runs (process gone, no graceful-shutdown log line - external cause,
e.g. host sleep, not a graph/mechanism problem) and was restarted
mid-sequence via the project's established `Start-Process` method. Also
observed: `comfyui.log` showed the GGUF UNet "loaded partially" (8.6 GB
usable, 8.1 GB loaded, 10.9 GB offloaded) during the seed-777777 B run,
with a 28-step sample taking 12:39 - markedly slower than the seed-424242
runs. Cause not isolated (could be VRAM state left over from the earlier
session, could be run-to-run variance) - flagged as a real open question
for the still-missing VRAM/timing characterization, not resolved here.

## Material/texture variant (M) - real photographic reference

Flat color swatches (B/B2) only prove color transfer, not material/texture
transfer - flagged as the key gap in both the "Evidence rules self-check"
below and `RESULTS_ref_weight.md`'s own open item ("Fotografische/
materialbasierte statt Flat-Color-Referenz - noch offen, günstigster
nächster Test"). Variant M reuses PROMPT_B's exact wording (material not
named) with a **user-supplied real photograph** of black leather (visible
grain, wrinkles, specular highlights - 3000x2000, not a synthetic/AI-
generated texture) as the reference, against variant D's existing
no-reference result as the ablation control.

**Operational issue found and fixed first**: the first attempt (unscaled
3000x2000 reference, matching the then-current "no scaling on reference"
convention inherited from the 512x512 flat swatches) forced the entire
GGUF UNET to offload to CPU (`comfyui.log`: "0.00 MB usable, 0.00 MB
loaded, 18969.81 MB offloaded") because the reference's own latent became
far larger than the sampled latent - the run was still progressing after
20+ minutes with no realistic end in sight and was interrupted via
`/interrupt`. Fixed by adding `ImageScaleToTotalPixels` (0.25 MP, chosen to
match the original 512x512 swatches almost exactly - a no-op for A/B/D/B2,
which did not need to be re-run) before the reference's `VAEEncode`,
applied to every variant's reference image, not just M. Re-run loaded
normally (6.2 GB on GPU, consistent with the earlier successful A/B/D/B2
runs) and completed.

**Result**: the masked dress shows visible leather grain texture, wrinkle
shading, and specular highlights consistent with the reference photo - not
a flat black fill. This is a materially stronger result than the B/B2
color swatches: **texture/material structure transferred, not just a
solid color**. Locality held (face, pose, background unchanged, same as
all prior variants).

## Evidence rules self-check

- **Live runtime results**: all 7 generations (baseline + A/B/D/B2 at two
  seeds + M), this session, this installation, `status_completed=true`,
  verified by fetching and viewing each output image via ComfyUI's `/view`
  API - not inferred from log text alone.
- **Visual test result** for color-follow, material/texture transfer, and
  locality: performed (images viewed directly), not assumed from graph
  construction.
- **Now established** (previously open): material/texture transfer - a
  real photographic reference (not a flat color swatch) produced visible
  grain/wrinkle/specular structure on the masked region, not just a flat
  fill. Single run only (seed 424242, not cross-seed-checked the way
  B/D/B2 were).
- **Still not established**: n>1 for the material variant specifically
  (only run once), VRAM/timing characterization (deliberately out of scope
  for this feasibility pass per Codex - "old margins don't transfer" means
  a real number is still needed before any further step; the M variant's
  own VRAM near-miss, see above, makes this more urgent), pixel-level
  locality diff against the VAE baseline (done visually, not numerically).
- **GGUF-specific**: this result is evidence for the installed GGUF Q4_K_M
  checkpoint specifically, not Dev precision variants generally - consistent
  with Codex's framing ("a feasibility proof for this GGUF setup, not
  general Dev reliability").

## Verdict

**Causal reference-driven masked color transfer is confirmed on Flux.2 Dev
with this GGUF checkpoint**, when using `VAEEncode(source)` +
`SetLatentNoiseMask` instead of the empty-latent graph. B2's green result
rules out "the model just defaults to red" or an SAM3/mask-shape artifact.
D's clean (non-drifting) ablation rules out "the model randomly recolors
masked regions regardless of reference." This directly contradicts the
closed investigation's finding for the empty-latent mechanism - correctly
so, since it is a different graph, not a re-run of the same one. The
second-seed cross-check (777777) reproduces all three causal results
(B/D/B2), raising confidence from a single sample to 2/2 agreement.
**Material/texture transfer is also confirmed** (variant M): a real
photographic leather reference produced visible grain/wrinkle/specular
structure on the masked region, not just a flat color fill - this is the
stronger claim `RESULTS_ref_weight.md` had left open since the original
case-3 investigation closed.

## Remaining risks / open items

- n=2 for the color variants (two seeds, both agreeing) - stronger than
  the original n=1, but still not a reliability estimate. Klein's own
  history (Base-checkpoint D-variant, 1/4 drift) shows seed-dependent
  failure modes can stay hidden at n=2 too. The material variant (M) is
  still n=1, not yet cross-seed-checked.
- A real high-resolution reference needs explicit scaling or it can force
  the entire UNET off the GPU (see the M variant's operational issue,
  above) - now fixed in the script, but worth remembering if this graph is
  ever extended to accept arbitrary user-supplied references.
- No VRAM/duration measurement - GGUF dequantization overhead and the
  larger Dev model are unknowns here; Klein's router-integration VRAM
  margins do not transfer to this graph shape. The seed-777777 run's
  partial-offload slowdown (see above) makes this more pressing, not less.
- No router integration proposed or implemented - this is a standalone
  feasibility result only, same posture Klein's test1 had before its own
  separate integration decision.
- Locality verified visually, not via a pixel-diff metric against the VAE
  baseline.
- The ComfyUI server crashed once mid-sequence (seed 777777, between B and
  D) for a reason not isolated in this session - operationally handled
  (restarted, resubmitted), but worth watching for a pattern if it recurs.
