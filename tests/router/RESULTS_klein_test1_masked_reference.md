# FLUX.2 Klein 9B (distilled fp8) + SAM3 masking: first clean image-based color transfer without text naming

Joint Claude-Codex decision (Codex exec session, read-only review of this
repo's masking results, the VTON sibling project's workflows, and the
current ComfyUI v0.38.0 source - see PROJECT_RULES.md's 2026-10-03 entries
for the full design discussion). Test script: `klein_test1_masked_reference.py`.

## Setup

Same mechanism proven for Qwen Image Edit 2511
(`RESULTS_masking_test2_current_env.md`): SAM3 mask ("the woman's dress") on
the source photo -> `SetLatentNoiseMask`. Swapped the editor for FLUX.2
Klein 9B (community fine-tune, `snofsSexNudesAndOtherFunStuff_distilledV12Fp8.safetensors`,
8.46 GB) with its native conditioning: plain `CLIPTextEncode` + two chained
`ReferenceLatent` nodes (source latent, then reference latent) - the same
native mechanism already used successfully for Flux.2 Dev
(`ab_flux2dev.py`), confirmed via `comfy/model_base.py` source reading to
not be a no-op for Klein (Klein loads as the same `Flux2(Flux)` class as
Dev, which inherits `reference_latents` handling from the `Flux` base
class - Claude's initial belief that Klein routes through an unrelated
"Lens" class, based on misreading a stale 2026-06-14 sibling-project note
written against ComfyUI v0.23.0, was wrong and self-corrected before any
GPU time was spent on it).

Settings per Codex's review: 4 steps, cfg=1 (BFL's official distilled-model
card recommendation, treated as a starting point for this community
fine-tune, not a guarantee), euler/simple, denoise=1.0 (full denoise inside
the SAM3 mask - the mask mechanism itself preserves everything outside, not
a reduced denoise value), Flux.2's own VAE (`flux2-vae.safetensors`, matches
this model's `latent_formats.Flux2`). No VLM caption stage, no post-hoc
color-correction - deliberately excluded so a pass/fail isolates the native
reference mechanism itself.

## Test matrix (Codex's design - causal, not just functional)

| Variant | Text names color? | Reference image | Result |
|---|---|---|---|
| A | yes ("red") | red swatch | Dress turned red |
| B | **no** | red swatch | **Dress turned red** |
| D | no | **none** | Dress stayed blue (source color, no spurious change) |
| B2 | **no** | **green swatch** | **Dress turned green** |

Same seed (424242), same mask, same prompt template, same sampling settings
across all four runs - only the reference image (and, for A, the text) varies.

## Result: positive, causally demonstrated

**B and B2 produced different outputs that each matched their respective
reference image's color, with identical prompts in both cases. D (no
reference) left the dress unchanged.** This is the first time in this
project's history (after Qwen Image Edit 2511 and Flux.2 Dev both failed
this exact test - see `RESULTS_masking_test2_current_env.md` and
`RESULTS_flux2dev_capability.md`) that image-based color transfer without
naming the color in text has been demonstrated with a clean causal control,
not just a single passing sample.

**Background preservation measured, not just eyeballed:** numeric pixel
diff of B2 and D against the source, in the same style as the Qwen masking
test's check - both variants show near-identical background noise floor
(B2: 6.65% of pixels with diff>30, mean diff 14.41/765; D: 6.72%, mean diff
12.68/765; top/bottom strip means 6-9 in both). The color change in B2 is
localized to the dress region; the background is equally stable whether the
run changes the dress (B2) or not (D).

## What this does NOT yet show (explicitly, per Codex's acceptance criteria)

- n=1 per variant, one source/reference pair, one mask, one seed - not a
  reliability screen.
- This is the community fine-tune checkpoint, not official BFL weights -
  the Base checkpoint (`flux-2-klein-base-9b.safetensors`, 16.91 GB, a
  separate non-distilled sampling profile per BFL's own documentation, not
  comparable at 4 steps) has not been tested yet - explicitly requested by
  the user, still open.
- No router integration - this is a standalone test script, not wired into
  `build_router_graph.py`.
- VRAM/timing not yet measured for this specific graph (no sampling loop
  attached to this run - add before treating this as cleared for any
  production use, same discipline as the Qwen masking tests).
- Flux.2 Dev + masking (the open item identified earlier today) is still
  untested - Codex noted Dev's existing graph samples from an empty latent,
  not the source latent, so adding a mask there needs a bigger graph change
  than just inserting `SetLatentNoiseMask`.
- Mask quality/robustness on other source/reference pairs, other garments,
  other colors - untested.

## Next steps (not yet done)

1. Repeat on the Base checkpoint (`flux-2-klein-base-9b.safetensors`) with
   its own, non-distilled sampling profile (BFL documents ~50 steps for
   Base, not 4) - explicitly requested by the user.
2. Add VRAM sampling (same method as `masking_test2_current_env.py`) to
   this test.
3. n>1 repeat-seed pass before calling this reliable rather than feasible.
4. Flux.2 Dev + masking, as its own separate test (needs the source-latent
   graph fix Codex identified).
