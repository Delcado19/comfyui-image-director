# Router integration: Qwen-Image-2.1 as a new `native_reference` edit mode

Joint Claude-Codex decision (two Codex exec rounds, 2026-10-05, read-only
review of `build_router_graph.py`, `tests/router/qwen_image21_reference_test1.py`,
`RESULTS_qwen_image21_reference_test1.md`, and the existing
`masked_reference` editor integrations). Implements `build_router_graph.py`
gaining a **new `edit_mode` value** (`"native_reference"`, alongside the
existing `"plain"` and `"masked_reference"`), with `editor="qwen_image21"`
as its only supported editor so far.

## Problem and observed state

`RESULTS_qwen_image21_reference_test1.md` had just validated, standalone,
that Qwen-Image-2.1's native `TextEncodeQwenImage21` node transfers a
reference image's color/material onto the dress without naming it in
text, outperforming every existing `masked_reference` editor (qwen/klein/
flux2_dev) on locality, causal color-follow, material transfer, speed, and
VRAM margin - including a literal recreation of this project's historical
"case 3" failure (real black-dress photo + blue reference + the exact
harmful prompt pattern, clean at n=2). Next step: make this callable
through the router.

## Claude's initial assessment

`TextEncodeQwenImage21` is structurally unlike every existing
`masked_reference` editor: no SAM3 mask, no `VAEEncode(source)` +
`SetLatentNoiseMask` anchoring - the sampled latent is fully empty
(`torch.zeros`), and locality comes entirely from the model's own Qwen3VL
multimodal understanding of "first image" vs. "second reference image".
It therefore needs neither `mask_target` (no SAM3 call exists) nor
`reference_description` (the model does not need the color/material named
- that was Qwen Image Edit 2511's masked-branch-specific requirement).
Forcing it into `edit_mode="masked_reference"` would be misleading: that
mode's own asserts currently require `mask_target` always and
`reference_description` for `editor="qwen"`, and the mode name itself says
"masked" when there is no mask. Initial lean: a new `edit_mode` value
(e.g. `"native_reference"`), exclusive to `editor="qwen_image21"`, capped
at exactly 1 reference image (matching what was actually validated, even
though the node's own schema supports up to 16).

## Codex's independent assessment

Agreed with the new-`edit_mode` approach in the first round (`"reference"`
alone rejected as too unspecific - `masked_reference` also processes
references) and confirmed the proposed contract (mode pairs exclusively
with `editor="qwen_image21"`, exactly 1 reference, no `mask_target`/
`reference_description`, caller still selects explicitly - no automatic
routing from `is_local_region`). Also independently flagged the Autogrow
dotted-key wiring risk as something to re-document prominently (easy to
silently get wrong again) and specified a concrete smallest-useful-test
shape (static structural check first, then real `build()` requests through
analyzer + lazy switch, checked against VRAM/log/output criteria).

**Material disagreement, raised and resolved:** Codex's first-round review
recommended wiring this branch's `prompt` input to `edit_prompt_str` (the
analyzer's own free-form output), to make the analyzer a real part of the
execution path. Claude objected: every validated result in
`RESULTS_qwen_image21_reference_test1.md` used the fixed, hand-written
`PROMPT_B` wording (or the deliberately-harmful `PROMPT_H`/`PROMPT_C3`
variants) - never the analyzer's `GUIDANCE`-driven free text - and the
existing `masked_reference` editors already establish the same precedent
(fixed templates, not `edit_prompt_str`, for their branch-specific
prompts) for the documented reason that the analyzer's free text is
unreliable for gating render behavior. Wiring an unvalidated
analyzer-prompt-reliability question onto a brand-new editor integration
stacks two untested variables at once. In a second exec round, Codex
agreed and reversed its recommendation: use the literal validated
`PROMPT_B` text, unparameterized, for this first integration - explicitly
scoping the branch as a dress-color/material-transfer path for now, not
general-purpose reference editing.

## Agreements

- New `edit_mode="native_reference"`, exclusive pairing with
  `editor="qwen_image21"` (asserted both directions).
- Exactly 1 reference image (`image2`); no `mask_target`/
  `reference_description` required.
- Caller still selects explicitly; no automatic routing.
- Fixed, unparameterized `QWEN21_PROMPT` (the validated `PROMPT_B`
  wording) - not `edit_prompt_str`, not a `mask_target`-style template.
- No dependency-injection scheduling gate needed: the router's existing
  lazy-switch guarantee (edit branch nodes cannot enter the pending
  execution set before the analyzer finishes) already covers this branch.
- Reuse the standalone script's exact settings unchanged (40 steps, CFG 1,
  Euler, `normal`, denoise 1.0, `resolution=1024`).

## Preferred solution (implemented)

`build()` gains `edit_mode="native_reference"` and `editor="qwen_image21"`.
When both are set: builds `qwen21_unet`/`qwen21_clip`/`qwen21_vae`
(`UNETLoader`/`CLIPLoader(type="qwen_image")`/`VAELoader`, paths matching
`qwen_image21_reference_test1.py`'s validated constants), `qwen21_encode`
(`TextEncodeQwenImage21` with `images.image_1`/`images.image_2` as direct
top-level **dotted** keys - not a nested `"images"` dict, the documented
Autogrow pitfall), `qwen21_sample` (`KSampler` using the encoder's own
positive/negative/latent outputs directly - no separate `EmptyLatentImage`
or masking node), and `VAEDecode` -> `edit_image`. No SAM3, no
`VAEEncode(source)`, no `SetLatentNoiseMask`, no reference image scaling
(the node resizes internally).

## Meaningful alternatives considered

- Reuse `edit_mode="masked_reference"` with exceptions for this editor -
  rejected; would make a named mode lie about its own mechanism and
  requires carving mask_target/reference_description exceptions into an
  already-established contract.
- Allow `editor="qwen_image21"` under `edit_mode="plain"` - rejected;
  `plain`'s contract explicitly says "always Qwen [2511]" project-wide, and
  the new editor's reference requirement does not fit that mode either.
- Wire `prompt` to `edit_prompt_str` for a "real" analyzer dependency -
  rejected after reconciliation (see disagreement above); no evidence
  exists that the analyzer's free text produces phrasing this specific
  node responds well to.
- A caller-supplied subject-description parameter (to generalize beyond
  "the dress") - deliberately deferred; would need its own validation
  pass, not covered by any test run so far.

## Evidence supporting the recommendation

See `RESULTS_qwen_image21_reference_test1.md` for the full standalone
causal test (color B/D/B2, material M, second-seed cross-check, the
historically-harmful-prompt-pattern test H, and the literal case-3
recreation C3 - all at n=2 per variant).

## Files changed

- `tests/router/build_router_graph.py`: `edit_mode="native_reference"` +
  `editor="qwen_image21"` option, module docstring entry (full design
  rationale, the Codex-reconciled prompt decision, the Autogrow wiring
  risk, explicit evidence-gap framing), new constants (`QWEN21_UNET_PATH`/
  `QWEN21_CLIP_PATH`/`QWEN21_VAE_PATH`/`QWEN21_PROMPT`), assert updates.
- `tests/router/qwen21_integration_test1.py` (new): first real end-to-end
  validation through the actual router (analyzer -> lazy switch ->
  branch), not just the standalone mechanism test.

## Validation performed

1. **Structural checks** (no GPU): assert guards confirmed in both
   directions (`editor="qwen_image21"` outside `native_reference` rejected;
   `native_reference` with any other editor rejected; 0 or 2 refs under
   `native_reference` rejected). A valid build produces exactly one output
   node (`save`), the Autogrow keys are the correct dotted top-level form
   (`images.image_1`/`images.image_2`, no nested `"images"` dict), encoder
   output indices 0/1/2 feed `positive`/`negative`/`latent_image`
   correctly, `edit_image` feeds the switch's `on_true`, and no `sam3_*`/
   `*noise_mask*` nodes are present anywhere in the graph.
2. **Generate-case lazy-switch check** (`qwen21_integration_test1.py
   generate`): instruction "Generate a picture of a quiet mountain lake at
   sunrise, no people." with `editor="qwen_image21"` wiring present
   (`edit_mode="native_reference"`, a reference image supplied, same
   wiring-present-but-unscheduled pattern used for Klein's and Dev's own
   integration tests). Analyzer picked `task="generate"`. Result: correct
   landscape image (`ImageDirector_router_00051_.png`), 16.3s wall time
   (Z-Image Turbo branch), **zero** `qwenImage21Nvfp4Q4`/`qwen3vl_8b_w4a8`
   log hits - the Qwen-Image-2.1 branch stayed entirely unscheduled,
   confirming the lazy switch holds with this editor wired in.
3. **Real edit-case runs through the router**
   (`qwen21_integration_test1.py edit_red` / `edit_green`): instruction
   "Change the color of the dress in this photo.", `editor="qwen_image21"`,
   source = blue-dress photo, references = the same red/green swatches
   used in the standalone causal test, seed 424243 (matching the
   standalone test's own seed for direct comparability). Analyzer
   correctly classified `task="edit"` both times. Results: dress turned
   red (`ImageDirector_router_00049_.png`) and green
   (`ImageDirector_router_00050_.png`) respectively, face/pose/background
   (street, buildings, trash can, beer bottle, bench) visually unchanged
   from the source in both - same locality/causal-follow behavior as the
   standalone script's B/B2 variants, now confirmed through the actual
   analyzer -> lazy-switch -> branch path, not just a hand-built graph.
   `status_completed=true`, no `[ERROR]` lines, both runs showed the
   expected `qwenImage21Nvfp4Q4`/`qwen3vl_8b_w4a8` log hits confirming the
   branch actually executed. Red variant: 38.9s wall time, 2146 MiB free
   minimum / 13,832 MiB used maximum - comfortably above the project's
   300 MiB floor, no mitigation gate needed. Green variant: 32.7s wall
   time (no VRAM sampling run on this one).

All of Codex's stated acceptance criteria for this first integration are
met: correct reference effect preserved through the router, measured VRAM
margin comfortably above the 300 MiB floor, confirmed lazy selection (both
generate-vs-edit and qwen_image21-vs-other-editor), no regression on
existing Qwen/Klein/Dev modes (the structural check confirms additive-only
node construction), analyzer-json and actual submitted prompt captured in
the saved graph/history JSON files for each run.

## Remaining risks

- n=1 per color at this exact router-integrated shape (one red run, one
  green run) - the standalone test's n=2-seed causal matrix does not
  automatically transfer to this specific graph instantiation, though the
  matching behavior (clean color-follow, preserved scene) is a good sign
  of faithful reproduction, same reasoning used for the Dev integration.
- No numeric locality check has been run for this mechanism anywhere in
  this project yet (standalone or router) - "scene unchanged" is a visual
  observation, same caveat as `RESULTS_qwen_image21_reference_test1.md`.
- No back-to-back-without-`/free` chain test for this router shape - every
  measurement so far (standalone and router) started from a clean `/free`
  baseline, same open gap already flagged for Dev's integration.
- The branch is explicitly scoped to dress-color/material transfer
  (`QWEN21_PROMPT` is a fixed, unparameterized template) - not yet a
  general-purpose reference-editing path; a caller-supplied subject
  parameter would need its own validation pass.
- Material (leather) and the literal case-3 recreation (C3) were validated
  standalone but not yet re-run through this router integration
  specifically - only the color B/B2 causal pair was re-verified here.
- Remains a third-party NVFP4 community quant, not an official
  Qwen-Image-2.1 release.
