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

**Disambiguated, then sized, by a repeat-seed sweep:** variant D repeated on
the Base checkpoint at three more seeds (same mask, same prompt, everything
else identical):

| Seed | Result | File |
|---|---|---|
| 424242 (original) | **Teal/petrol drift** | `ImageDirector_KleinTest1_base_00003_.png` |
| 777777 | Stayed blue | `ImageDirector_KleinTest1_base_00005_.png` |
| 111111 | Stayed blue | `ImageDirector_KleinTest1_base_00006_.png` |
| 555555 | Stayed blue | `ImageDirector_KleinTest1_base_00007_.png` |

**Final at n=4: 1/4 seeds (25%) showed the teal drift, 3/4 showed clean
preservation.** This confirms (a) seed-specific sampling noise rather than
(b) a systematic Base-vs-distilled behavioral difference - the "no reference
-> no change" guarantee is not reliably broken on Base, but it is also not
as airtight as the single distilled-checkpoint sample suggested: with no
reference latent anchoring the unmasked-color prior, Base's full 34-step
denoise inside the mask can occasionally drift at some seeds even though the
prompt gives it no positive reason to change color. n=4 is still a small
sample (a true ~25% rate has wide uncertainty at this n - anywhere from
roughly 5% to 55% would not be surprising), but it is now large enough to
say the drift is real and non-trivial, not a one-off fluke, while also
confirming most seeds do preserve color correctly. `PROMPT_D2` (added to
`klein_test1_masked_reference.py`, not yet run) rewords the no-reference
prompt to not reference a nonexistent "second reference image" ("Keep the
masked dress unchanged. Do not alter its color or material.") as an untested
mitigation candidate for this drift - worth testing before relying on Base's
no-reference masked-edit behavior in any production use.

**Timing observed (not yet systematically measured):** roughly 17-27 minutes
wall-clock per run on this GPU, dominated by the 34-step `dpmpp_sde` sampling
loop (~30-42s/it observed via the stderr progress bar) rather than model
loading (the UNET/CLIP/VAE loaders cache after the first run). One run
(B2) exceeded the test script's 1800s client-side poll timeout by ~16s even
though it completed successfully server-side - the script's `timeout_s=1800`
for the Base profile is too tight and should be raised (e.g. to 2400s)
before further Base-checkpoint runs.

## VRAM/timing test (distilled checkpoint, variant B) - with vs. without `mask_save`

Codex's recommended smallest test before any router integration decision
(read-only Codex exec session, 2026-10-04): Codex flagged that this
standalone script's `mask_preview`/`mask_save` pair is an extra
`OUTPUT_NODE=True` execution root that `build_router_graph.py`'s
`masked_reference` wiring deliberately omits (to keep the generate/edit lazy
switch working), so the standalone script's own VRAM/scheduling shape might
not represent the router's actual topology. New script:
`klein_vram_test1.py`, reusing `klein_test1_masked_reference.build()`'s new
`include_mask_preview` parameter. Also replaces the prior VRAM-sampling
method (`masking_test2_current_env.py`'s per-sample `nvidia-smi` respawn,
which had real gaps up to 1.2-1.4s despite requesting 250ms) with a single
long-lived `nvidia-smi --loop-ms=100` process - verified below to produce
genuinely continuous ~109ms sampling, closing that measurement gap. Both
conditions started from a clean `POST /free` cold floor (not cached), per
Codex's instruction and this project's established VRAM-test methodology.

| Condition | Wall time | Peak VRAM used | Min free VRAM | Sample gap (min/mean/max) | Samples |
|---|---|---|---|---|---|
| `with_mask_save` (standalone shape) | 19.6s | 15257 MiB | **721 MiB** | 0.106s / 0.109s / 0.113s | 186 |
| `no_mask_save` (router's actual shape) | 16.1s | 15766 MiB | **212 MiB** | 0.105s / 0.109s / 0.114s | 154 |

(Total VRAM on this card is 16303 MiB; `used + free` accounts for ~16303 -
~325 MiB in both conditions, consistently, matching a fixed OS/driver/other-
process baseline outside ComfyUI's own accounting.)

**Sampling quality:** both conditions hit ~109ms mean spacing with a tight
0.105-0.114s range - the new loop-mode sampler fixes the prior method's
1.2-1.4s gap problem outright; the un-sampled blind spot between any two
points is now bounded to roughly 110ms, not over a second.

**Important, counter-intuitive finding: removing `mask_save`/`mask_preview`
made the VRAM margin WORSE, not better.** Peak usage rose from 15257 to
15766 MiB (+509 MiB) and the minimum free margin dropped from 721 to 212
MiB when going from the standalone shape to the router's actual shape. This
is not what a naive "fewer nodes = less memory" intuition would predict -
removing those two cheap nodes evidently shifts ComfyUI's scheduling/
allocator timing such that other buffers (likely VAE decode and/or sampler
tensors) peak-overlap more than they did when mask_save's own execution
gave the allocator a different ordering to work with. This was not derived
analytically, just observed - the actual mechanism is not established here.

**This means the number that matters for router integration is 212 MiB, not
721 MiB, and 212 MiB is below the ~300 MiB safety margin this project has
otherwise treated as the acceptable floor (see the router's own
back-to-back-chain VRAM results, `RESULTS_RVchain.md`/`RESULTS_RVref.md`).**
At n=1, this is one sample, not a proven worst case - the real floor could
be tighter still (the unsampled gap between any two of the ~109ms-spaced
points) or this run could be an unlucky outlier. This did not by itself
clear Codex's stated acceptance criteria for an opt-in router integration
attempt - the back-to-back chain test below was run to find out whether 212
MiB is typical or an outlier.

### Back-to-back chain (no `/free` between runs)

Three `no_mask_save` runs in a row, only the first starting from `/free`,
matching how the router would actually be hit by consecutive real requests
(per Codex's explicit recommendation and this project's established
back-to-back-chain discipline). **First attempt was invalid and is not
reported as data**: using the identical seed/graph for all three runs made
ComfyUI's own node-level caching turn runs 2 and 3 into near-instant cache
hits (0.5s wall time, `execution_cached` listed all 18 nodes including the
KSampler itself) - this measured nothing about real back-to-back VRAM
behavior and was caught before being written up. Fixed by giving each chain
run a different seed (424243/424244/424245): this still lets the UNET/CLIP/
VAE/SAM3 loaders stay cached across runs (as real back-to-back router
traffic would), while forcing genuine re-execution of sampling, VAE decode,
and SaveImage each time.

| Run | Seed | Wall time | Peak VRAM used | Min free VRAM |
|---|---|---|---|---|
| 1 (fresh from `/free`) | 424243 | 15.7s | 15611 MiB | 367 MiB |
| 2 (back-to-back) | 424244 | 6.7s | 13803 MiB | **2175 MiB** |
| 3 (back-to-back) | 424245 | 7.2s | 13809 MiB | **2169 MiB** |

**Verdict: the margin gets better across the chain, not worse.** The first
post-`/free` execution is the tight point (367 MiB here vs. 212 MiB in the
earlier single-run measurement - two independent samples of the same
condition straddling the ~300 MiB threshold, consistent with real n=1-2
variance, not a contradiction). Runs 2 and 3 - genuine back-to-back
executions with no `/free` between them - both land above 2100 MiB free,
a large and stable improvement over run 1. The likely mechanism (not proven
here, just a plausible read): the first execution after `/free` pays a
one-time cost - CUDA context/allocator warmup, PyTorch's caching allocator
building its memory pool, SAM3's first load - that subsequent back-to-back
requests don't repeat once that pool exists. **This reframes the earlier
concern: the risk is concentrated in the first request after a VRAM-clearing
event (server start, a `/free` call, or a different heavy workload having
just evicted this graph's models), not in sustained back-to-back router
usage, which this data suggests is actually safer than the cold-start case.**
Two independent cold-start samples (212 MiB, 367 MiB) both sit close to or
under the 300 MiB floor - that first-request risk is not resolved and
should still gate any router integration decision, but it is a narrower,
better-understood problem than "back-to-back usage degrades VRAM margin,"
which this chain test does not support.

This is still a single 3-run chain (not repeated chains) and the cold-start
condition has only n=2 - both would benefit from more samples before
treating either number as a stable estimate, but the qualitative finding
(back-to-back doesn't make things worse; cold-start is the tight point) is
unlikely to flip with more data given how large the gap is (367/212 MiB vs.
2100+ MiB).

## Next steps (not yet done)

1. ~~Quantify the Base checkpoint's no-reference color-drift rate~~ - done
   (n=4: 1/4 drift, see above). `PROMPT_D2` (reworded prompt) remains
   untested as a mitigation candidate.
2. Test `PROMPT_D2` (the reworded no-reference prompt) - not yet tried.
3. ~~Raise `timeout_s` for the Base profile~~ - done (2400s).
4. ~~Add VRAM sampling~~ - done for the distilled checkpoint's masked_reference
   mechanism (see VRAM/timing section above), **not yet done for the Base
   checkpoint**.
5. ~~Re-measure the router-representative (`no_mask_save`) VRAM condition
   back-to-back without `/free`~~ - done (see Back-to-back chain subsection
   above). Finding: back-to-back usage is NOT the risk (margin improves to
   2100+ MiB); the cold-start-after-`/free` case is the tight point (n=2:
   212, 367 MiB, straddling the ~300 MiB floor). **Still open: more
   cold-start samples (n>2) to pin down whether the first-request margin is
   reliably above or below the safety floor**, and/or a mitigation (not
   loading SAM3 and the Klein UNet/CLIP simultaneously, reserve-vram-style
   headroom) before this is safe to gate a router go/no-go decision on.
6. n>1 repeat-seed pass on the A/B/B2 (reference-present) variants too,
   before calling either checkpoint's positive result reliable rather than
   feasible.
7. Flux.2 Dev + masking, as its own separate test (needs the source-latent
   graph fix Codex identified).
