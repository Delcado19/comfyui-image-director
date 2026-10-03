# FLUX.2 Klein 9B + SAM3 masking: first clean image-based color transfer without text naming

Covers both checkpoints the user asked to test: the distilled fp8 community
fine-tune (below) and the official BFL Base checkpoint (own section further
down), both run through the same A/B/D/B2 causal matrix.

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
- This is the community fine-tune checkpoint, not official BFL weights.
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

## Base checkpoint (`flux-2-klein-base-9b.safetensors`, 16.91 GB) - same A/B/D/B2 matrix

Requested by the user alongside the distilled checkpoint from the start
("mit der destilled und base variante"). Settings taken directly from the
installed official `Flux.2 klein 9B-Base Basic Workflow.json` example (not
guessed): `RandomNoise` + `CFGGuider` (cfg=4) + `KSamplerSelect`
(`dpmpp_sde`) + `Flux2Scheduler` (34 steps, 1024x1024) +
`SamplerCustomAdvanced`, in place of the distilled profile's plain
`KSampler` (4 steps, cfg=1, euler/simple). Same mask, same seed (424242),
same source/reference images as the distilled run.

| Variant | Text names color? | Reference image | Result |
|---|---|---|---|
| A | yes ("red") | red swatch | Dress turned red |
| B | **no** | red swatch | **Dress turned red** |
| D | no | **none** | **Dress turned teal/petrol-green - did NOT stay blue** |
| B2 | **no** | **green swatch** | Dress turned vivid green (clearly distinguishable from D's teal) |

Output files (`E:\AI_Art\`): A = `ImageDirector_KleinTest1_base_00002_.png`,
B = `ImageDirector_KleinTest1_base_00001_.png`, D =
`ImageDirector_KleinTest1_base_00003_.png`, B2 =
`ImageDirector_KleinTest1_base_00004_.png`. All four visually inspected
directly (no numeric pixel diff run yet for the Base set).

**A and B replicate the distilled checkpoint's positive result**: both
reference-present variants turned the dress red regardless of whether the
color was named in text, matching the causal pattern already established.

**D is an open divergence from the distilled checkpoint, not a clean
negative control.** With no reference image attached, the prompt still
reads "Change only the masked dress to match the second reference image. Keep
everything outside the mask unchanged." - there is no second reference for
the model to match. On the distilled checkpoint this produced no change
(dress stayed the source blue). On the Base checkpoint, at the same seed,
the dress changed to a teal/petrol-green that matches neither the source
blue nor any reference actually supplied - the Base model appears to have
treated the dangling "second reference image" phrase as license to invent a
color rather than leaving the region alone. B2's green is visibly distinct
from D's teal (greener, more saturated, closer to the actual swatch), so the
reference signal is still doing *something* directionally - but D shows the
"no reference -> no change" guarantee that held for the distilled checkpoint
does not automatically hold for Base.

**Disambiguated by a reseed run:** repeated variant D on the Base checkpoint
at seed 777777 (same mask, same prompt, everything else identical) -
`ImageDirector_KleinTest1_base_00005_.png`. Result: the dress stayed the
source blue, same as the distilled checkpoint's D result. So at n=2 seeds,
1/2 showed the teal drift and 1/2 showed clean preservation. This points to
(a) seed-specific sampling noise rather than (b) a systematic Base-vs-distilled
behavioral difference - the "no reference -> no change" guarantee is not
reliably broken on Base, but it is also not as airtight as the single
distilled-checkpoint sample suggested: with no reference latent anchoring the
unmasked-color prior, Base's full 34-step denoise inside the mask can
occasionally drift at some seeds even though the prompt gives it no positive
reason to change color. This is still n=2 - not enough to quantify a drift
rate - but it reframes the finding from "Base behaves differently from
distilled" to "Base's no-reference case has some non-zero color-drift risk
that a single sample doesn't capture reliably." A larger repeat-seed sweep
(n>=5) would be needed to estimate how often this happens, and the prompt
reword suggested below has not been tested as an independent mitigation.

**Timing observed (not yet systematically measured):** roughly 17-27 minutes
wall-clock per run on this GPU, dominated by the 34-step `dpmpp_sde` sampling
loop (~30-42s/it observed via the stderr progress bar) rather than model
loading (the UNET/CLIP/VAE loaders cache after the first run). One run
(B2) exceeded the test script's 1800s client-side poll timeout by ~16s even
though it completed successfully server-side - the script's `timeout_s=1800`
for the Base profile is too tight and should be raised (e.g. to 2400s)
before further Base-checkpoint runs.

## Next steps (not yet done)

1. Quantify the Base checkpoint's no-reference color-drift rate with a
   larger repeat-seed sweep (n>=5) now that n=2 shows it is real but not
   universal (1/2 seeds drifted).
2. Test whether rewording the no-reference prompt (e.g. "Keep the masked
   dress unchanged" instead of referencing a nonexistent "second reference
   image") reduces or eliminates the drift - not yet tried.
3. ~~Raise `timeout_s` for the Base profile~~ - done (2400s).
4. Add VRAM sampling (same method as `masking_test2_current_env.py`) to
   this test, for both checkpoints.
5. n>1 repeat-seed pass on the A/B/B2 (reference-present) variants too,
   before calling either checkpoint's positive result reliable rather than
   feasible.
6. Flux.2 Dev + masking, as its own separate test (needs the source-latent
   graph fix Codex identified).
