# Masking mechanism reproduction under current environment + router integration (2026-10-03)

Joint Claude-Codex decision (Codex exec session, read-only review of this
repo, no file access). Context: user asked to wire the proven SAM3 +
`SetLatentNoiseMask` masking mechanism (`RESULTS_masking_test1.md`,
2026-08-05) into the production router (`build_router_graph.py`), after
~2 months of project inactivity.

## Environment drift found before any test was run

ComfyUI was upgraded v0.29.2 -> v0.38.0 during the pause (commit `6b747c04`,
fresh `comfyui_scan` from today). Live-verified via `GET /object_info`
(checking actual returned content, not just HTTP status - an earlier draft
of this check made exactly the shallow-check mistake this project's own
history already warned about, caught and redone):

- Qwen Image Edit 2511 UNet: GGUF file deleted, replaced by
  `diffusion_models/Qwen Image Edit 2511/qwen_image_edit_2511_fp8.safetensors`
  (`UNETLoader`, not `UnetLoaderGGUF`).
- Its abliterated text encoder: GGUF -> `text_encoders/Qwen Image Edit 2511/
  qwen2.5_vl_7b_huihui_abliterated_fp8.safetensors` (`CLIPLoader`,
  `type="qwen_image"`, not `CLIPLoaderGGUF`).
- Z-Image Turbo's CLIP: GGUF gone, replaced by `Z-Image/
  Lockout-Qwen3-4b-heretic-v2.safetensors` (`CLIPLoader`, `type="lumina2"`).
- VAE folder renamed `Flux.1 & Z-Image` -> `Flux.1 - Z-Image - HiDream`.
- `LoadJsonFromText`/`GetTextFromJson` (comfyui-art-venture) are
  quarantine-disabled (`custom_nodes/_quarantine.disabled/comfyui-art-venture`)
  - not re-enabled without asking why. Replaced with the core node
    `JsonExtractString` (`comfy_extras/nodes_string.py`), which also
    collapses two nodes into one.
- This project's synthetic/photo test fixtures (`IMG_7148.jpg`,
  `imgdir_test_ref2.png`, `imgdir_jsontest_shapes.png`) no longer exist in
  ComfyUI's `input/` directory - not recoverable as pixel data. Substitutes
  used instead: `imgdir_masktest2_source_bluedress.png` (the original
  masking_test1's own successful output - a real photo, everything outside
  the dress claimed/now measured near-identical to the original source) and
  a newly generated flat `imgdir_masktest2_ref_red.png` swatch.
- `easy sam3ModelLoader`'s combo metadata is broken via the API (returns the
  literal characters C/O/M/B/O instead of a filename list) - the model file
  itself (`models/sam3/sam3.safetensors`) is unchanged on disk and the
  known-good value still submits successfully; this is an API-introspection
  bug in `comfyui-easy-sam3` after the ComfyUI upgrade, not a missing file.

## Standalone reproduction (`masking_test2_current_env.py`)

Same mechanism as `RESULTS_masking_test1.md` (SAM3 mask on "the woman's
dress" -> `SetLatentNoiseMask` -> `TextEncodeQwenImageEditPlus` with a
mask-aware prompt), new fixtures (blue dress -> red swatch instead of the
original black -> blue).

**Result: mechanism reproduced successfully** with the new safetensors
loaders. Dress recolored red, rest of scene visually unchanged, consistent
with the original.

**New measurements the original test didn't have (with caveats added after
Codex's post-implementation review of this doc and the saved CSVs):**
- VRAM (fresh `/free`, full execution, `execution_cached.nodes: []`):
  worst *sampled* margin **760 MiB free** (16 GB card). The sampling loop's
  actual gaps between samples ran up to ~1.2-1.4s, not the requested 250ms
  (nvidia-smi subprocess overhead) - 760 MiB is a real observed minimum,
  not a proven worst-case floor; a lower, unsampled trough is possible.
  SAM3 loaded and fully released before the editor's own ramp in this n=1
  sample - not proven to be guaranteed by the graph topology (see router
  integration section).
- A background-region pixel comparison (ad-hoc, not part of the saved
  script, ran as a one-off check): mean absolute diff in the top/bottom 150
  pixel rows (sky/ground, chosen as a visual proxy for "outside the mask",
  not the actual mask complement) was ~5 out of 765 possible, vs. ~16
  overall. Supports "background looks near-unchanged" with an actual
  number instead of eyeballing, but it is a strip sample, not a full
  outside-mask pixel audit, and the check is not reproducible from this
  script as committed.
- Mask visualization was fixed: the original script's `mask_preview` node
  read `easy sam3ImageSegmentation`'s output index 1, which `GET
  /object_info` confirms is named `images` - a plain passthrough of the
  input image, not a mask overlay. It never showed the actual mask. Fixed
  here via `MaskToImage` on output 0 (`masks`). The real mask, once
  visualized, is a visually partial/odd shape that does not look like full
  dress coverage - yet the whole dress recolored correctly in both runs.
  Not explained (plausibly latent-space downsampling tolerance); flagged as
  an open question, not a failure, since the outcome was correct both times.

**Ablation (remove the explicit color word "red" from the prompt, same
mask/seed/everything else):** dress turned **black**, not red. Note (Codex
review): the two prompt variants differ by more than the single word
"red" - `PROMPT_MASKED_NO_COLOR` also drops "and material" and rewords
"match the ... of" to "match ... of" - so this is not the single-variable
isolation the original Flux.2 Dev ablation was. What's actually shown:
this specific reworded, color-name-free prompt failed to transfer the
reference's color, consistent with (but not an independently controlled
re-confirmation of) the project's existing pattern
(`RESULTS_flux2dev_capability.md`). Masking does not fix this; it only
fixes locality.

## Router integration (`build_router_graph.py`)

Per the joint decision (see that file's module docstring for full
rationale): added an explicit `edit_mode: "plain" | "masked_reference"`
parameter, decided at graph-build time by the caller - never from the
analyzer's own plan fields (`is_local_region`/`edits[]` are documented as
unreliable gating signals). `masked_reference` requires explicit
`mask_target` and `reference_description`, and exactly 1 reference image.

Also fixed in the same pass (same root cause, not a scope-creep addition):
the plain generate branch's `gen_clip`/`gen_vae` paths, which hit the exact
same GGUF-removal/folder-rename drift and would have blocked even an
unmodified router run.

**Live-validated end-to-end, 3 submissions against the real ComfyUI
instance, all `status_completed: true`, fresh execution (no cache) where
checked:**
1. Plain generate (`edit_mode` default): Z-Image Turbo branch, produced a
   correct image; VRAM shape and output confirm the edit branch (and SAM3)
   never loaded.
2. Plain edit (no masking): Qwen Image Edit 2511 branch, completed
   successfully with the new fp8 loaders.
3. `masked_reference` edit: analyzer correctly classified the instruction as
   `task="edit"`, lazy switch selected the edit branch, SAM3 mask + masked
   prompt template produced the same red-dress result as the standalone
   script - now proven through the actual router/switch architecture, not
   just the isolated test. Worst *sampled* VRAM margin 888 MiB free (same
   sampling-gap caveat as above - up to ~1.2-1.4s between samples, so this
   is an observed minimum, not a proven floor). VRAM shape (two separate
   load/release bumps - analyzer, then SAM3 - before
   the final sustained ramp) shows no overlap in this n=1 sample; the
   generate branch's own models never loaded (no third bump).

**4th live run, closing Codex's two post-implementation-review blockers:**
`build()` called with its own new `source_image` parameter directly (not a
post-hoc graph-dict override) and `edit_mode="masked_reference"` wiring
present, but a GENERATE-classified instruction ("a green vintage car...").
Completed in 24.5s; VRAM shows only two phases (analyzer, then the generate
branch's own ramp) - no SAM3-scale load/release bump, unlike every masked-
edit run. Confirms SAM3 stays unexecuted when the masked wiring exists in
the graph but generate is selected, not only when `edit_mode="plain"`
omits the wiring outright. Output correct (a green vintage car).

**Not validated / explicitly out of scope for this step** (per the joint
decision's accepted risks):
- Execution order between SAM3 and the editor's own CLIP/UNet load is not
  *guaranteed* by the graph topology (no data dependency forces it, unlike
  the E2/E3 negative-prompt fix) - only empirically fine in these n=1/n=2
  samples. Do not treat `masked_reference` as cleared for back-to-back
  production use without a dedicated VRAM-chain test (same category as the
  existing mandatory `/free`-between-requests rule for the plain edit
  branch).
- Automatic detection of when masking is needed - still fully manual
  (`edit_mode`/`mask_target`/`reference_description` are caller-supplied).
- Mask quality/robustness on images other than this one source/reference
  pair.
- The project's other stale test-fixture paths (synthetic shapes image,
  the many `tests/router/*.py` A/B scripts still pointing at deleted
  GGUF files) - out of scope for this pass, flagged as a separate pending
  cleanup.
