# Closing the remaining-risks list: router-integrated Qwen-Image-2.1

Follow-up to `RESULTS_router_qwen21_integration.md`'s "Remaining risks"
section. Four items were testable; two are scope decisions, not test gaps
(the fixed dress-only prompt, the community quant) and stay as documented
limitations, not addressed here.

Scripts: `qwen21_integration_test2.py` (second seed, material, C3 fixture,
back-to-back chain, all through the actual router), `qwen21_mask_gen.py`
(standalone SAM3 dress masks, measurement-only), `qwen21_locality_numeric.py`
(pixel-diff math). `qwen_image21_reference_test1.py` gained a `D3` variant
(black-dress ablation) as the C3 fixture's numeric baseline.

## 1. n=1 per color -> n=2 (second seed through the router)

Seed 777777, same red/green references, through the actual router (not the
standalone script). Both completed, `status_completed=true`, no `[ERROR]`
lines, `qwenImage21Nvfp4Q4`/`qwen3vl_8b_w4a8` log hits confirmed the branch
executed. Dress turned red / green respectively; face, pose, and background
visually unchanged from the source - same behavior as the first router
seed (424243) and the standalone script's own second-seed cross-check.
**2/2 consistent at the router-integrated shape now, not just n=1.**

- red, seed 777777: 36.4s, 2397 MiB free minimum / 13,581 MiB used maximum.
- green, seed 777777: 32.8s (no VRAM sampling run on this one).

## 2. Material (M) and the C3 fixture, through the router

**Material**: leather reference, seed 424243, through the router. Visible
grain/wrinkle/specular structure on the dress, scene preserved (face,
pose, street, trash can, bench, buildings) - same quality as the
standalone test's M variant, now confirmed through the analyzer -> lazy
switch -> branch path. 34.6s, 2429 MiB free minimum / 13,549 MiB used
maximum.

**C3 fixture**: the real black-latex-dress photo (person, outdoor Cannes
scene) + blue reference swatch, through the router - using the router's
own **fixed, safe** `QWEN21_PROMPT`, NOT the standalone script's harmful
`PROMPT_C3` wording. The router cannot send that harmful pattern at all
(the prompt is a hardcoded, unparameterized template by design - see
`build_router_graph.py`'s docstring) - so this tests "does the mechanism
generalize to a different real photo/color pair through the router's own
production prompt", not a re-test of the harmful-prompt-pattern robustness
itself. That robustness result (variant H/C3 in
`RESULTS_qwen_image21_reference_test1.md`) remains standalone-only, and
this does not claim otherwise. Result: dress turned a clean saturated
blue, face/hair/pose/roses/foliage/sea/mountains visually unchanged - same
quality as the standalone C3 result. 32.8s, 2461 MiB free minimum /
13,517 MiB used maximum.

## 3. Back-to-back-without-`/free` chain

3 edits in a row through the router, only the first gets a clean `/free`
floor, alternating red/green reference (varying only the seed was found
insufficient to force genuine re-execution in Klein's own chain test - the
encode node has no seed dependency either here) - mirrors
`klein_integration_test1.py`'s chain methodology exactly.

| run | ref | seed | wall time | VRAM free min | VRAM used max |
|---|---|---|---|---|---|
| chain_edit_1 | red | 424244 | 32.5s | 2397 MiB | 13,581 MiB |
| chain_edit_2 | green | 424245 | 31.3s | 2461 MiB | 13,517 MiB |
| chain_edit_3 | red | 424246 | 31.0s | 2461 MiB | 13,517 MiB |

All 3 produced distinct output files (`ImageDirector_router_00056/57/58_.png`)
confirming genuine re-execution each run, not a cached repeat.
`qwen21_executed=true` for all three; `qwen21_cached=true` for runs 2-3
(the UNET/CLIP/VAE loaders legitimately cache - same paths every run,
exactly like Klein's own loaders - not a lazy-switch violation).
**VRAM margin held steady across all 3 runs (2397-2461 MiB free), no
degradation over repeated back-to-back traffic**, comfortably above the
project's 300 MiB floor without any mitigation gate.

## 4. Numeric locality check (pixel diff vs. D-ablation baseline)

Per-pixel max-channel absolute difference between each edit and its own
run's D (no-reference ablation, same seed/source) baseline, restricted to
OUTSIDE a SAM3-segmented dress mask - **adapted from**
`RESULTS_flux2dev_masking_test1.md`'s methodology, not identical to it:
Dev/Klein anchor sampling on the source's own VAE-encoded latent, so a
pure VAEEncode->VAEDecode "baseline" is the right reconstruction floor for
them. `TextEncodeQwenImage21` samples from a **fully empty latent** (see
`qwen_image21_reference_test1.py`'s docstring) - there is no VAE-anchored
reconstruction in this mechanism's own graph to diff against. D (an
independent full regeneration with no reference attached, same seed) is
the correct comparator instead - matching how D was already used as the
visual ablation baseline throughout `RESULTS_qwen_image21_reference_test1.md`.
The dress mask itself is not part of the router graph (this editor uses
none) - generated once per source image, standalone, by `qwen21_mask_gen.py`,
purely as a measurement tool, then resized (nearest-neighbor) to each
output's actual resolution before diffing.

| variant | mean diff | p99 diff | max diff | % px > 10 | % px > 25 |
|---|---|---|---|---|---|
| red, seed 424243 | 3.83 | 23.0 | 143 | 5.59% | 0.77% |
| green, seed 424243 | 3.63 | 22.0 | 104 | 5.38% | 0.64% |
| red, seed 777777 | 3.43 | 21.0 | 137 | 4.31% | 0.60% |
| green, seed 777777 | 3.32 | 20.0 | 177 | 4.30% | 0.58% |
| material (leather) | 3.77 | 22.0 | 106 | 5.63% | 0.65% |
| C3 fixture | 4.04 | 51.0 | 143 | 9.22% | 2.51% |

**This is measurably worse than Dev's own numeric locality result** (Dev's
p99 ranged 8-11, % px > 10 ranged 0.5-1.2%, see
`RESULTS_flux2dev_masking_test1.md`) - roughly 2x the p99 and 4-8x the
%-over-10 rate, with the C3 fixture (busier background: railing, roses,
foliage) worse still. **This corrects
`RESULTS_qwen_image21_reference_test1.md`'s "outperforms every masking-
based approach ... on every axis measured" claim** (a dated correction was
added there) - that was true for every axis actually measured at the time
(locality was still only a visual impression then), but does not hold for
this specific numeric axis now that it has been measured.

**Spatial check (not just the aggregate numbers)**: generated diff
heatmaps for the red/seed-424243 and C3-fixture cases (per-pixel diff
magnitude outside the mask, visualized as grayscale). Both show the
elevated-diff pixels concentrated in a **thin outline right at the dress
silhouette boundary**, plus faint fine-detail edges in the background
(fence/railing lines, foliage, building windows, hair strands, facial
features) - not a diffuse wash or color tint spreading across the sky,
distant buildings, or other large uninvolved regions. This is consistent
with the mechanism difference documented above: independently regenerating
the whole image from noise produces a few-pixel silhouette shift and
fine-detail resampling noise between any two runs, inflating boundary-
adjacent and high-frequency-detail pixels, without the diffuse bleeding
case-3's original failure mode showed (global tint across the entire
frame, flagged explicitly in `RESULTS_content_quality.md` - this is a
qualitatively different, much more localized kind of drift).

**What this does and does not establish**: establishes that Qwen-Image-2.1's
numeric per-pixel stability outside the edited region is lower than Dev's
VAE-anchored mechanism, concentrated at edges/fine detail rather than
diffuse bleeding - a real, now-quantified trade-off against the mechanism's
other advantages (speed, VRAM margin, graph simplicity, no masking
infrastructure, and the qualitative "does it actually look like the same
photo" impression, which remains strong). Does not establish whether this
specific gap matters for any real use case - that depends on how much
pixel-exact stability a given application needs outside the edited region,
a question this project has not yet defined a threshold for.

## Updates to `RESULTS_router_qwen21_integration.md`

The "Remaining risks" items this closes:
- n=1 per color in the router-integrated shape -> now n=2 (seeds 424243,
  777777, both through the router).
- No numeric locality check -> now measured (see above) - with the
  important correction that it does NOT favor Qwen-Image-2.1 over Dev on
  this specific axis, unlike every other measured axis.
- No back-to-back-without-`/free` chain test -> now run (3 edits, VRAM
  margin held steady).
- Material/C3 validated standalone but not through the router -> both now
  run through the router (C3 using the router's own safe prompt, not a
  re-test of the harmful-pattern robustness specifically).

Still open, by design (not test gaps): the fixed dress-only prompt scope,
and the third-party NVFP4 community quant.

## Files

- `tests/router/qwen21_integration_test2.py` - second seed, material, C3
  fixture, and back-to-back chain, all through the router.
- `tests/router/qwen21_mask_gen.py` - standalone SAM3 dress masks for
  numeric scoring (not part of the router path).
- `tests/router/qwen21_locality_numeric.py` - the pixel-diff computation.
- `tests/router/qwen_image21_reference_test1.py` - gained a `D3` variant
  (black-dress ablation, the C3 fixture's numeric baseline).
