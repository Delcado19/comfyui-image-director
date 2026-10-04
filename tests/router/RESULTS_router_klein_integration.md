# Router integration: FLUX.2 Klein 9B distilled as an opt-in `masked_reference` editor

Joint Claude-Codex decision across two Codex exec rounds (read-only review
of `build_router_graph.py`, the full `klein_test1_masked_reference.py` /
`RESULTS_klein_test1_masked_reference.md` causal-test and VRAM-mitigation
history, and this file's own validation runs). Implements
`build_router_graph.py`'s `editor` parameter (`"qwen"` default |
`"klein_distilled"`), meaningful only for `edit_mode="masked_reference"`.

## Problem and observed state

`build_router_graph.py`'s existing `masked_reference` mode is built
entirely around Qwen Image Edit 2511, which requires the reference's
color/material to be named in text (`reference_description`).
`klein_test1_masked_reference.py` proved FLUX.2 Klein 9B distilled performs
the same masked color/material transfer *without* naming the color -
causally demonstrated (A/B/D/B2 matrix, n=3-5 depending on variant) - but
that mechanism was only validated standalone, not through the router's
analyzer -> lazy-switch -> branch architecture, and its VRAM margin
(212-967 MiB cold-start, n=5) was marginal against this project's ~300 MiB
safety floor.

## Claude's initial assessment

Additive integration (new `editor` selector, Qwen stays default) is lower
risk than replacing Qwen's masked_reference path outright, since Klein has
not been checked against the specific Qwen masking use cases already in
production use, and reversibility matters more than elegance for a first
attempt. The VRAM margin needed a real fix (not just more measurement)
before this was safe to ship.

## Codex's independent assessment (round 1)

Agreed with the additive approach and identified a methodological gap
before implementation: the standalone test's `mask_save`/`mask_preview`
pair is an extra `OUTPUT_NODE=True` execution root the router's wiring
deliberately omits (to preserve the lazy generate/edit switch), so the
standalone script's VRAM/scheduling shape might not represent the router's
actual topology. Recommended re-measuring without those nodes before
deciding.

## Codex's independent assessment (round 2, after new evidence)

Caught two errors in the first VRAM-mitigation attempt: (1) it measured the
Base checkpoint, not the actual integration target (distilled); (2) gating
the unload only on positive conditioning doesn't guarantee negative
encoding has finished. Also confirmed `PixaromaFreeVram` (which worked well
in isolation) is unsafe for router use - its `OUTPUT_NODE=True` would
execute its Klein-encoding dependency chain even when the runtime analyzer
picks "generate". Recommended `VRAM_Debug` (no such flag) with full
`unload_all_models=True`, properly gated on both encodings, verified via
log correlation rather than assumed-safe graph position.

## Agreements

- Additive `editor` selector, `masked_reference` only, Qwen stays default
  and untouched.
- No `FluxKontextImageScale` for the Klein branch - unscaled source,
  matching what was actually validated (scaling is a separate, untested
  question).
- No `reference_description` requirement for Klein - its proven prompt
  template deliberately omits the color/material description.
- VRAM mitigation is required, not optional, before this ships.
- Exactly one final `edit_image` output root, regardless of editor.

## Areas of disagreement, and how resolved

- Round 1 vs round 2 VRAM evidence: Claude's first mitigation test ran on
  the wrong checkpoint and used an incomplete ordering gate; both were
  caught by Codex's review, not found independently - corrected before
  implementation, not during it.
- `PixaromaFreeVram` vs `VRAM_Debug`: Claude's first result favored
  Pixaroma (bigger single-run effect); Codex's architectural objection
  (`OUTPUT_NODE=True`) is decisive regardless of effect size, since it is a
  correctness problem (unconditional eviction on every generate-branch
  request), not a performance one - resolved in favor of `VRAM_Debug`.

## Preferred solution (implemented)

`build()` gains `editor: str = "qwen"`. When `editor == "klein_distilled"`
and `edit_mode == "masked_reference"`: builds `klein_unet`/`klein_clip`/
`klein_vae` loaders (paths matching `klein_test1_masked_reference.py`'s
validated `PROFILES["distilled"]`), `klein_src_latent`/`klein_ref_latent`
(unscaled `VAEEncode`), `klein_pos_text` (literal
`KLEIN_MASKED_PROMPT_TEMPLATE.format(target=mask_target)`, no description
slot) chained through two `ReferenceLatent`s (source then reference), a
type-safe ordering gate (`SomethingToString` + `StringSubstring(start=0,
end=0)`) forcing `klein_neg_text` to encode only after the positive chain
completes while still encoding the same `""` it always used, `VRAM_Debug
(unload_all_models=True, gc_collect=True, empty_cache=True)` gated on the
negative chain (so gated on both encodings transitively), a 4-step
`euler`/`cfg=1` `KSampler` (matching the validated distilled profile), and
`VAEDecode` -> `edit_image`. SAM3 segments the unscaled `src` image (not
`edit_scale`, which does not exist in this branch). None of the new nodes
are `OUTPUT_NODE=True`.

## Meaningful alternatives considered

- Replace Qwen's masked_reference path entirely with Klein - rejected
  (Codex: Klein has not been checked against Qwen's existing accepted use
  cases; no evidence basis to retire a working path).
- Ship without a VRAM mitigation, documenting the ~20% cold-start-OOM risk
  as a known limitation - rejected once a working, router-safe mitigation
  (`VRAM_Debug`) was found; no reason to accept avoidable risk.
- `PixaromaFreeVram` as the mitigation - rejected, confirmed
  `OUTPUT_NODE=True` architectural conflict with the lazy switch.

## Evidence supporting the recommendation

See `RESULTS_klein_test1_masked_reference.md`'s VRAM-mitigation section for
the full round-1/round-2 measurement history and `comfyui.log` correlation
proving CLIP was genuinely GPU-resident at the gate point before the unload
fired (369 -> 2333 MiB free, distilled checkpoint, properly gated).

## Files changed

- `tests/router/build_router_graph.py`: `editor` parameter, module
  docstring entry, Klein branch construction, assert updates
  (`reference_description` now optional for `editor="klein_distilled"`).
- `tests/router/klein_integration_test1.py` (new): first real end-to-end
  validation through the actual router (analyzer -> lazy switch -> branch),
  not just the standalone mechanism test.

## Validation performed

1. **Structural regression check** (no GPU): `editor="qwen"` (default) for
   both `edit_mode="plain"` and `edit_mode="masked_reference"` produces
   graphs with no `klein_*` nodes present - the new parameter is additive
   and does not alter existing Qwen-path node construction.
2. **Real edit-case run through the router** (`klein_integration_test1.py
   edit`): instruction "Change the color of the dress in this photo.",
   `editor="klein_distilled"`, source = blue-dress photo, reference = red
   swatch (same fixtures as the standalone test). Analyzer correctly
   classified `task="edit"`. Result: dress turned red
   (`ImageDirector_router_00038_.png`), `status_completed=true`, no
   `[ERROR]` lines in `comfyui.log`. Log confirms the VRAM gate fired and
   freed 8.42 GB (`VRAMdebug: freed memory: 8,422,970,516`) - matching the
   standalone mitigation test's result - before the UNET loaded.
3. **Generate-case lazy-switch check** (`klein_integration_test1.py
   generate`): instruction "Generate a picture of a quiet mountain lake at
   sunrise, no people." with the *same* `editor="klein_distilled"` graph
   wiring present. Analyzer picked `task="generate"`. Result: a correct
   landscape image (`ImageDirector_router_00039_.png`, no people), and
   `comfyui.log` shows **zero** Klein/SAM3/`VRAMdebug` log lines for this
   run - the Klein branch, including its VRAM-mitigation side effect,
   stayed entirely unscheduled, confirming the lazy generate/edit switch
   still holds with the new branch present.

All of Codex's stated acceptance criteria for the first integration
attempt are met: correct transfer, measured VRAM margin, confirmed lazy
selection, no regression on existing Qwen modes.

## Remaining risks

- n=1 for both the VRAM-gated mitigation and this end-to-end router test -
  a repeat-seed pass (same discipline already applied to the standalone
  Klein tests) would still be worth doing before calling this reliable
  rather than feasible, especially given the standalone test's own n=4
  D-variant sweep found a real (if non-dominant) seed-dependent failure
  mode on the Base checkpoint; the distilled checkpoint's positive variants
  showed 0 failures at n=3, but that is not proof of 0% at larger n.
  Base checkpoint is explicitly out of scope for this integration (Codex,
  round 2) - not available as an `editor` choice.
- Back-to-back-without-`/free` VRAM behavior was proven safe for the
  *standalone* distilled masked_reference graph
  (`RESULTS_klein_test1_masked_reference.md`'s back-to-back chain test,
  margin improves not degrades) but not yet re-verified for this exact
  router-integrated graph shape (extra nodes: the string-gate pair,
  `VRAM_Debug`, SAM3 on `src` instead of `edit_scale`) under repeated
  real router traffic.
- Image-scaling question (whether the Klein branch should eventually gain
  its own `FluxKontextImageScale`-equivalent for consistency or for
  resolution/cost reasons) deliberately deferred, per Codex's explicit
  "smaller, evidence-based first port" guidance - unscaled only, for now.
- `comfyui.log`-based `klein_executed` detection in
  `klein_integration_test1.py` is a reasonable but informal signal (string
  matching on log lines), not a structural guarantee from ComfyUI's own
  execution API - sufficient for this validation, not a permanent
  regression-test mechanism.
