# Router integration: Flux.2 Dev (GGUF Q4_K_M) as an opt-in `masked_reference` editor

Joint Claude-Codex decision (Codex exec consultation, 2026-10-04, read-only
review of `build_router_graph.py`, `tests/router/flux2dev_masking_test1.py`,
`RESULTS_flux2dev_masking_test1.md`, `RESULTS_router_klein_integration.md`,
and `PROJECT_RULES.md`'s case-3 history). Implements `build_router_graph.py`'s
`editor` parameter gaining a third value (`"flux2_dev"`, alongside the
existing `"qwen"` default and `"klein_distilled"`), meaningful only for
`edit_mode="masked_reference"`.

## Problem and observed state

`tests/router/flux2dev_masking_test1.py` had just validated, standalone,
that Flux.2 Dev (GGUF Q4_K_M) + `VAEEncode(source)` + `SetLatentNoiseMask`
causally transfers both color and material/texture structure onto a masked
region without naming it in text - a capability `ab_flux2dev.py`'s
empty-latent graph had been conclusively shown NOT to have
(`RESULTS_flux2dev_capability.md`). The user asked to integrate this into
the router, the same way FLUX.2 Klein 9B distilled was integrated earlier
(`editor="klein_distilled"`, see `RESULTS_router_klein_integration.md`).

## Claude's initial assessment

Before consulting Codex, flagged a real concern: Dev's masked edit takes
~828-840s (roughly 14 minutes) per the standalone test, versus Klein's
~15-25s for the equivalent router operation - a 30-40x order-of-magnitude
difference. Also: both masking tests used the same easy fixture
(blue dress, color swatches/leather photo), not the harder case-3 content
that originally motivated this entire investigation (the case where the
user judged Klein "isn't capable enough" - `PROJECT_RULES.md`), so no
evidence exists that Dev produces BETTER results than Klein on any real
case. Initial framing: is integration even well-motivated given Klein
already solves the same problem, much faster, with no proven quality
upside for Dev?

## Codex's independent assessment

Corrected a wrong assumption in Claude's framing: the router's `editor`
parameter is **already a manual, caller-set choice** - the analyzer only
ever decides `generate` vs. `edit`, never which editor. So there is no
"automatic 14-minute surprise" risk; whoever calls `build()` with
`editor="flux2_dev"` does so deliberately, same as `"klein_distilled"`.

Separated two different questions: (1) **technical integration** - making
a validated mechanism callable through the router - versus (2) **model
preference** - choosing Dev over Klein based on quality. Sufficient
evidence exists for (1); essentially none exists for (2), and (1) does not
require (2) to be resolved first. Also independently confirmed, by reading
the code, a real gap Claude had not yet checked: `flux2dev_masking_test1.py`'s
`build()` defaults `include_mask_preview=True` and `run_variant()` never
overrode it, so the existing 2049 MiB VRAM figure was NOT router-
representative (the same `OUTPUT_NODE=True` lesson already learned for
Klein's own round-1 integration review).

## Agreements

- Technical integration is justified now; a Klein-vs-Dev quality
  comparison is a separate, future question and does not block this.
- Additive `editor="flux2_dev"` selector, `masked_reference` only, Qwen
  stays default and untouched, Klein stays available and untouched.
- Reuse Dev's exact validated wiring and settings (cfg=1.2, 28 steps,
  `dpmpp_sde`, `Flux2Scheduler`, `SamplerCustomAdvanced`/`CFGGuider`) - do
  NOT port Klein's 4-step `KSampler` or `VRAM_Debug` mitigation gate
  uncritically; Dev's own measured VRAM margin does not need one.
- The known long runtime and the material-identity softness (unambiguous
  "leather" at only 1 of 2 tested seeds) must stay visibly documented, not
  buried under a generic "feasibility confirmed" summary.
- The router-unrepresentative VRAM figure needed re-measurement before
  integration, not after.

## Preferred solution (implemented)

`build()` gains a third `editor` value, `"flux2_dev"`. When
`editor == "flux2_dev"` (only valid for `edit_mode="masked_reference"`):
builds `dev_unet`/`dev_clip`/`dev_vae` loaders (`UnetLoaderGGUF`/
`CLIPLoader`/`VAELoader`, paths matching
`flux2dev_masking_test1.py`'s validated constants), `dev_src_scale`
(`ImageScaleToTotalPixels`, 1 MP - matches `ab_flux2dev.py`'s own
convention) feeding `dev_get_size` and `dev_src_latent`, `dev_ref_scale`
(0.25 MP - **not optional**, an unscaled high-resolution reference forced
the entire UNET off the GPU in the standalone test, a proven failure mode)
feeding `dev_ref_latent`, `dev_pos_text` (literal
`DEV_MASKED_PROMPT_TEMPLATE.format(target=mask_target)`, no description
slot, same wording as Klein's) chained through two `ReferenceLatent`s
(source then reference), `dev_neg_base`/`dev_neg_ref_src` (zeroed text +
source `ReferenceLatent`, no mitigation gate needed), `dev_noise`/
`dev_scheduler`/`dev_sampler_select`/`dev_guider`/`dev_sample`
(`SamplerCustomAdvanced`, unchanged Dev settings), and `VAEDecode` ->
`edit_image`. SAM3 segments `dev_src_scale` (not the raw `src` - mask and
latent must share spatial dimensions). No `mask_save`/`mask_preview` -
same lazy-switch reasoning as the Qwen and Klein branches. None of the new
nodes are `OUTPUT_NODE=True`.

## Meaningful alternatives considered

- Defer router integration until a Klein-vs-Dev quality comparison exists
  on harder content - rejected for now (Codex: the user's explicit
  integration request is a valid reason for the technical step alone;
  model-preference evidence can follow later without blocking it).
- Port Klein's `VRAM_Debug` mitigation gate defensively, "just in case" -
  rejected; Dev's own measured margin (1645-1673 MiB free, ~5.5x above the
  300 MiB floor) does not need it, and adding an untested gate would be
  speculative, not evidence-based.
- Port Klein's 4-step sampler settings for speed - rejected; never tested
  for Dev, and Dev's own validated settings are the only evidence-backed
  choice for this first integration.

## Evidence supporting the recommendation

See `RESULTS_flux2dev_masking_test1.md` for the full standalone causal
test (color + material transfer, numeric locality check, VRAM/timing
history including the router-representative re-measurement:
840.4s/1645 MiB free at seed 777777, `--no-mask-preview`).

## Files changed

- `tests/router/build_router_graph.py`: `editor="flux2_dev"` option,
  module docstring entry (full design rationale, explicit non-default/
  non-quality-claim framing, visible runtime/material-identity caveats),
  new constants (`DEV_UNET_PATH`/`DEV_CLIP_PATH`/`DEV_VAE_PATH`/
  `DEV_MASKED_PROMPT_TEMPLATE`), assert updates.
- `tests/router/flux2dev_integration_test1.py` (new): first real
  end-to-end validation through the actual router (analyzer -> lazy switch
  -> branch), not just the standalone mechanism test.

## Validation performed

1. **Structural regression check** (no GPU): `editor="qwen"` (plain and
   masked_reference) and `editor="klein_distilled"` produce graphs with
   zero `dev_*` nodes - the new option is additive and does not alter
   existing node construction. `editor="flux2_dev"` produces 19 `dev_*`
   nodes, zero `klein_*` nodes, no `mask_save`/`mask_preview`, SAM3
   correctly wired to `dev_src_scale`.
2. **Generate-case lazy-switch check**
   (`flux2dev_integration_test1.py generate`): instruction "Generate a
   picture of a quiet mountain lake at sunrise, no people." with
   `editor="flux2_dev"` wiring present (`edit_mode="masked_reference"`,
   same pattern as Klein's own generate-case test). Analyzer picked
   `task="generate"`. Result: correct landscape image
   (`ImageDirector_router_00047_.png`), 26.4s wall time (Z-Image Turbo
   branch, not Dev), **zero** Dev/SAM3 log hits - the Dev branch stayed
   entirely unscheduled, confirming the lazy switch holds with this editor
   wired in.
3. **Real edit-case run through the router**
   (`flux2dev_integration_test1.py edit`): instruction "Change the color
   of the dress in this photo.", `editor="flux2_dev"`, source =
   blue-dress photo, reference = the real leather photo (same fixtures as
   the standalone material test). Analyzer correctly classified
   `task="edit"`. Result: masked dress shows the same non-flat,
   wrinkle/sheen-structured transfer as the standalone test
   (`ImageDirector_router_00048_.png`), `status_completed=true`, no
   `[ERROR]` lines. 841.1s wall time, 1673 MiB free minimum / 14,305 MiB
   used maximum - consistent with the standalone router-representative
   re-measurement (840.4s / 1645 MiB), confirming the router wiring
   reproduces the validated standalone mechanism faithfully, not just
   approximately.

All of Codex's stated acceptance criteria for this first integration
attempt are met: correct reference effect, preserved locality (consistent
with the standalone numeric check), measured VRAM margin comfortably above
the 300 MiB floor, confirmed lazy selection (both generate-vs-edit and
Dev-vs-other-editor), no regression on existing Qwen/Klein modes.

## Remaining risks

- n=1 for this exact router-integrated shape (one edit-case run) - the
  standalone test's n=2-seed color/material results do not automatically
  transfer to this specific graph instantiation, though the matching
  VRAM/timing figures are a good sign of faithful reproduction.
- Material *identity* (not just structure) remains seed-sensitive per the
  standalone test (1 of 2 seeds unambiguously read as "leather") - not
  re-tested at a second seed through the router specifically.
- No back-to-back-without-`/free` chain test for this router shape (Klein's
  own integration needed one to catch a real VRAM-margin question - not
  yet done here). Every measurement so far, standalone and router, started
  from a clean `/free` baseline.
- No head-to-head Dev-vs-Klein quality comparison on harder content exists
  - this integration proves the mechanism is callable through the router,
  not that Dev should ever be preferred over Klein for any specific case.
- Runtime (~14 minutes) makes this unsuitable for any interactive/
  low-latency use without the caller being aware - documented here and in
  the module docstring, not hidden.
- Server crash cause from the standalone test's seed-777777 run (between B
  and D) remains unexplained - not reproduced during this integration's
  validation runs, but not ruled out either.
