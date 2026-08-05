# Codex Instructions

Read `PROJECT_RULES.md` before analyzing this project.

Also read the project sources in this order:

1. `docs/source/IMAGE_DIRECTOR_AUDIT.md`
2. `docs/source/COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`

When the documents conflict, the newer technical audit has priority unless
newer verified runtime evidence supersedes it.

Do not silently carry outdated conclusions from the older handover into a new
decision.

## Role

Codex is:

- an equal technical reasoning partner with Claude
- an independent architect and analyst
- a critical discussion partner
- a read-only reviewer of completed changes

Claude coordinates the interaction because the user communicates through
Claude Code.

Claude is the only agent permitted to modify files.

The read-only restriction concerns file operations only. It does not make
Codex subordinate in architectural, technical or diagnostic decisions.

Codex should challenge Claude's assumptions when evidence supports a different
conclusion.

Do not agree merely to produce consensus.

## Independent analysis

Before responding to Claude's proposal, inspect the available evidence
independently.

Identify:

- observed current state
- likely causes or architectural issues
- supporting evidence
- plausible solution options
- objections to likely approaches
- risks
- missing evidence
- smallest useful test

Do not simply restate Claude's analysis.

Do not assume Claude's preferred solution is correct.

If Claude supplies a conclusion without enough evidence, identify the missing
evidence explicitly.

## Joint decision process

For a meaningful technical or architectural decision:

1. Perform an independent analysis.
2. Present your own preferred solution and reasoning.
3. Identify meaningful alternatives.
4. State objections to Claude's proposal where applicable.
5. Distinguish:
   - agreement
   - disagreement
   - unsupported assumptions
   - unresolved uncertainty
6. Respond directly to Claude's counterarguments in follow-up calls.
7. Revise your position when new evidence justifies it.
8. Maintain disagreement when the evidence still supports a different
   conclusion.
9. Propose a controlled test when discussion alone cannot resolve the issue.
10. Help define acceptance criteria before implementation.

The goal is a supported joint conclusion, not automatic agreement.

Do not treat a single exchange as sufficient when material disagreements remain.

## Required output for a proposed decision

Report:

1. Observed current state
2. Your independent diagnosis
3. Concrete supporting evidence
4. Claude assumptions you agree with
5. Claude assumptions you challenge
6. Preferred solution
7. Meaningful alternatives
8. Smallest testable next step
9. Validation procedure
10. Acceptance criteria
11. Rollback considerations
12. Unresolved risks

Keep recommendations within the current task's scope.

Prefer the smallest useful change over a large redesign.

Do not bundle unrelated recommendations.

## File modification restriction

When invoked through Claude Code, remain read-only.

Do not:

- create files
- modify files
- produce or apply patches
- create backups
- stage changes
- create commits
- create branches
- push changes
- change ComfyUI configuration
- install or download dependencies
- alter repositories

You may propose:

- concrete code
- complete file contents
- algorithms
- workflow structures
- node layouts
- validation commands
- migration or rollback procedures

Claude must evaluate and implement any approved file changes.

## Required review after implementation

Review the completed change independently.

Check:

- whether the approved scope was respected
- whether unrelated files changed
- whether the implementation matches the joint decision
- whether complete workflow JSON remains valid
- whether links and node inputs are intact
- whether node classes actually exist
- whether model paths actually exist
- whether loader assumptions are supported
- whether rollback remains possible
- whether tests support the claimed result
- whether runtime or visual validation is still missing

Identify findings by severity:

- Blocker
- Important
- Minor
- Informational

Do not report speculative concerns as confirmed defects.

If Claude disagrees with a review finding, examine Claude's evidence and respond
to it directly.

Revise or withdraw a finding when the evidence disproves it.

Maintain the finding when the objection does not resolve the underlying issue.

## Evidence requirements

Base conclusions on concrete evidence from:

- project documents
- actual ComfyUI files
- installed custom-node source code
- workflow JSON
- command output
- runtime logs
- controlled tests
- user-supplied visual test results

Distinguish clearly between:

- verified facts
- source-code findings
- live runtime results
- visual test results
- historical findings
- assumptions
- recommendations
- joint consensus
- unresolved disagreement

Consensus between Claude and Codex is not proof by itself.

A model file being present does not prove that it loads or runs correctly.

A loader class being installed does not prove compatibility with a specific
checkpoint.

Disk size does not prove simultaneous VRAM usage.

Do not claim image quality, identity preservation, edit locality or performance
without an actual controlled runtime test.

## ComfyUI-specific reasoning rules

- Do not invent node names or node classes.
- Do not assume a node is functional solely because it appears in inventory.
- Check complete workflow structure rather than isolated fragments.
- Flag dangling links and unconnected required inputs.
- Preserve known-good workflow sections.
- Treat the production ComfyUI installation as customized and fragile.
- Do not recommend resetting dirty repositories.
- Do not recommend installing a new node pack before checking existing nodes.
- Keep GGUF and safetensors paths logically separate.
- Keep model and text-encoder switching separate where required.
- Do not add SageAttention fallback paths unless explicitly requested.
- Treat FLUX.2 as outside the Version-1 critical path unless the current task
  explicitly concerns it.
- Treat the Qwen2.5-VL-7B GGUF analyzer path (`AILab_QwenVL_GGUF_Advanced`)
  as loader- and runtime-smoke-tested (`docs/source/IMAGE_DIRECTOR_AUDIT.md`
  §13, Test A and Test C) — not merely inventory-present. **The underlying
  text-encoder weights changed 2026-08-03** (swapped to an
  abliterated/uncensored GGUF, `Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf`,
  see `PROJECT_RULES.md`'s "Current architecture status") and Qwen Image
  Edit 2509 was replaced by 2511 the same day (full swap, not an A/B) - both
  changes were independently runtime-smoke-tested afterward and succeeded
  (analyzer correctly described the standard shapes test image; the new
  UNet+CLIP pair correctly executed a real edit, blue-square removal,
  verified visually). Test A/C's/E2/E3's *specific VRAM margin numbers*
  still predate these swaps and have not been re-measured with the new file
  sizes - don't assume those exact numbers hold, even though basic
  loading/inference is now confirmed working.
- File paths hardcoded in this project's own test scripts
  (`tests/vram/combined-multiref/`, `tests/schema/analyzer-json*/`) and the
  sibling `comfyui-qwenvl-structured-gguf` repo's probes are stale after
  the 2026-08-03 model swaps and will fail if re-run without updating
  `MODEL_PATH`/`MMPROJ_PATH` first - do not treat their historic outputs as
  reproducible with the current install, only as a historical record.
- Do not infer structured JSON output, plan quality, or image quality from
  Test A/C alone. Structured JSON *shape* has its own separate, passing
  tests (see below) - plan/content quality and image quality remain
  separately unresolved, not covered by any test yet. The router's
  *routing mechanism itself* is now separately tested and passing (see the
  V1 task router bullet below) - it is not inferred from Test A/C, it has
  its own direct evidence.
- For structured edit-plan JSON output specifically, use `QwenVLStructuredGGUF`
  (external repo `comfyui-qwenvl-structured-gguf`, MIT, junction-installed
  into `custom_nodes`, not yet Comfy Registry published), not prompt-only
  `AILab_QwenVL_GGUF_Advanced` — prompt-only structural output was tested
  and failed 0/3 (`tests/schema/analyzer-json/`, historical/superseded).
  `QwenVLStructuredGGUF` grammar-constrains output via
  `response_format`/`llama-cpp-python`, validated 4/4 structurally in this
  project's own first-party test (`tests/schema/analyzer-json-structured/`).
  `docs/schema/edit_plan.grammar.schema.json` is the `oneOf`-restructured,
  grammar-converter-compatible variant of `edit_plan.schema.json` (that
  converter does not support `if`/`then`) — use it, or an
  availability-narrowed variant of it, not the canonical `if`/`then` file,
  when constructing a `response_format.schema` value.
- Structural JSON reliability being solved does not mean plan/content
  quality is solved — keep these separate. `is_local_region` has been
  observed flipped on an otherwise structurally-valid response, and
  `reference_slots` has been observed referencing an image that was never
  provided when the schema permitted it (mitigated by using an
  availability-specific schema per call, not by trusting the model). Do not
  claim edit-plan quality, routing correctness, or image quality from a
  structural pass alone.
- Treat the V1 task router's *routing mechanism* as built and smoke-tested
  end-to-end (`tests/router/RESULTS_router_v1.md`,
  `tests/router/RESULTS_lazy_switch.md`, `tests/router/build_router_graph.py`):
  one graph, one queue press, `QwenVLStructuredGGUF` -> `task` extraction ->
  `easy compare` -> `easy ifElse` lazily selects Z-Image Turbo (generate) or
  Qwen Image Edit 2511 (edit), confirmed via log analysis (only the selected
  branch's components loaded) and visual inspection of the output (matched
  the instruction) in both directions, n=1 per direction. Scoped to the
  single-source-image case at the time of this test - multi-reference
  routing has since been implemented (see below). Do not claim reliability
  beyond n=1 or plan/content quality from this test; those remain
  separately unresolved as documented elsewhere in this file and in
  `PROJECT_RULES.md`.
- VRAM margins for the router graph itself ARE now measured
  (`tests/vram/router/RESULTS_RV.md`) - both directions show the same
  clean analyzer-peak/trough/branch-peak shape as the non-router path, no
  sampled overlap. Z-Image Turbo (generate) has comfortable margin (2391
  MiB free, single brief spike). **Qwen Image Edit 2511 (edit) is tight:
  954 MiB free, sustained ~37s** - passes this project's 300 MiB threshold
  but is the tightest margin recorded for any passing VRAM test here, per
  Codex review "now the real binding constraint." At the time of this test
  multi-reference (`image2`/`image3`) routing had not been built; it has
  since passed cold-floor VRAM and been characterized back-to-back (see
  the multi-reference bullet below). Also: neither branch's models unload
  after a run completes (both stay GPU-resident).
- **Analyzer-load gap fixed:** `QwenVLStructuredGGUF` (external repo
  `comfyui-qwenvl-structured-gguf/nodes/structured_gguf_vl.py`) got an
  opt-in `free_vram_before_load: BOOLEAN` (default `False`) that calls
  `comfy.model_management.unload_all_models()` + `soft_empty_cache()`
  right before loading a genuinely new model - it loads via direct
  `llama_cpp.Llama(...)`, outside `comfy.model_management`, so it
  otherwise cannot trigger eviction of stale resident weights itself. Set
  `True` only in the router graph's analyzer node
  (`tests/router/build_router_graph.py`); every other caller stays at
  `False`. Repeating `RESULTS_RVchain.md`'s exact back-to-back-no-`/free`
  scenario with the fix (n=2, `tests/vram/router/RESULTS_RVfix.md`)
  confirms it: the analyzer's load no longer stacks on resident weights,
  and the original 901 MiB near-miss location does not recur.
- **Hard rule still in force, root cause moved (see `PROJECT_RULES.md`'s
  mandatory safety rules): do not use the V1 router for repeated
  back-to-back requests without `POST /free` between them**, even with
  the analyzer fix applied. The same n=2 RVfix test found the *edit
  branch's own* diffusion load/`KSampler` phase is now the tightest point
  instead - 271 MiB free (run 1), 238 MiB free (run 2), both below this
  project's 300 MiB floor, both log-confirmed `full load: True` with no
  errors/OOM. Root cause not isolated (could be `QwenImage`'s own
  footprint, allocator state after the back-to-back sequence, or residual
  effects of the analyzer's own eviction call - Codex was explicit this
  isn't proven independent of the fix). No code fix proposed for this
  second finding - accepted mitigation is the same `/free`-between-
  requests rule; an isolated (no preceding request) edit-only run still
  only measured 456 MiB free, so even a cold edit branch has limited
  margin on this 16 GB card. **`--reserve-vram 2.5` validated as a working
  alternative mitigation** (`tests/vram/router/RESULTS_reservevram.md`):
  moves the worst tested margin (196 MiB) to 2410 MiB by forcing partial
  UNet loading, at a real ~1.5-2x speed cost. Verified mechanism (traced
  `load_models_gpu()` in `model_management.py`), n=1 on the hardest case
  only. Not adopted as default - ComfyUI restored to standard launch
  right after the test, per the user's explicit preference. **User
  decision (2026-08-04): not adopting `--reserve-vram` permanently** - the
  speed cost isn't worth it project-wide. `/free`-between-requests remains
  the settled default policy; `--reserve-vram` stays available as a
  verified fallback lever, not the plan.
  **Multi-reference makes this worse, not better:** a 2-reference
  generate -> edit back-to-back sequence (`RESULTS_RVrefchain.md`)
  measured **196 MiB free (run 1), 463 MiB free (run 2)** - the worse of
  which is the tightest margin recorded in this project - despite the
  isolated multi-reference margin (916 MiB) being roomier than the
  isolated single-image margin (456 MiB). The back-to-back sequencing cost
  is larger for multi-reference than for single-image, opposite of what
  the isolated numbers alone predict; the spread between the two runs
  (196 vs. 463) is itself evidence this scenario isn't stable enough to
  call safe without `/free`.
- **Plan/content quality: first real-photo look done**
  (`tests/router/RESULTS_content_quality.md`), n=1x3, not a reliability
  screen. Local object removal and global restyle passed both the
  structured plan and the visual output on a real photo. A multi-reference
  color-match case failed visually (whole image tinted instead of just the
  targeted garment) and its plan had real issues (`is_local_region` likely
  wrong, `images.image2.role: "source"` - see the new schema gap below,
  the recurring `"entire image"`/`"full image"` placeholder overuse). Per
  Codex's review, do not assert the plan bugs *caused* the visual
  failure - the router only consumes `task`/`prompt` from the plan,
  `edits[]`/`preserve[]`/`images[].role` are generated but never read
  downstream (case 1's bad `edits[]` didn't break its correct visual
  result, proving this). **Schema gap fixed (same session):** reference
  slots could legally claim `role: "source"` -
  `edit_plan_schema.py`'s `_IMAGE_SLOT` role enum is now narrowed
  (`REFERENCE_ROLE_ENUM_ORDERED`, excludes `"source"`), validator updated
  to match, self-tested with no regression on the 5 previously-saved
  outputs. Re-testing case 3 confirmed the fix (`image2.role` is now
  `"object_reference"`) - its visual output also happened to pass this
  time, but per Codex, do not credit the schema fix for that, since the
  render path still doesn't consume `images[].role`; the more likely
  cause is prompt-wording variance between the two analyzer samples (see
  `RESULTS_content_quality.md`'s "Update" section). **This wording
  hypothesis was later isolated and confirmed** via a standalone,
  analyzer-bypassing A/B test (same seed/images, only the prompt's
  "background" clause varied): "a solid blue background" reproduced the
  whole-image tint, "a solid blue" gave the correct dress-only result -
  see `tests/router/RESULTS_ab_background_word.md`. Not confirmed to
  generalize beyond this one image/prompt pair. **Follow-up fix attempt
  failed:** a `GUIDANCE` clause telling the analyzer to avoid
  "background"/"backdrop" wording did not suppress the word at n=1 and the
  visual retest still failed (differently); reverted, not adopted. **A
  second follow-up fix attempt also failed:** a hand-written negative
  prompt ("background, sky, buildings, pavement, environment, skin, hair,
  pose, face") wired into the always-empty `edit_cond_neg` did not rescue
  the bleed on the confirmed-bad positive wording - dress stayed
  unrecolored, scene tinted blue either way (empty vs. handwritten
  negative, no visible difference); see
  `tests/router/RESULTS_ab_negative_prompt.md`. Prompt-level mitigations
  (analyzer guidance, negative prompt) are considered exhausted for now
  (2026-08-05, joint Claude-Codex review) - a current limitation, not
  permanent. **Deterministic-prompt-construction candidate tested and
  rejected before implementation:** an analyzer-only n=5 test (no image
  generation, `tests/router/analyzer_field_reliability.py`) checked
  whether `is_local_region`/`edits[].subject`/`.region` are reliable
  enough to build the render prompt from, instead of the free `prompt`
  field. They are not - `is_local_region` was wrong (`false`) in 5/5, and
  `edits[0]` was `{"subject": "entire image", "region": "full image"}` in
  5/5 (the exact placeholder overuse already flagged as an open item),
  worse than `prompt` (usable in 3/5). Not built - see
  `tests/router/RESULTS_analyzer_field_reliability.md`. `is_local_region`
  misclassification and `"entire image"`/`"full image"` placeholder
  overuse remain open, unfixed; the remaining candidates are
  masking/region-conditioning or a dedicated analyzer-quality fix for
  these two fields, neither started. **Analyzer-quality follow-up
  (2026-08-05):** re-tested a separately-reverted 2026-08-03 wording+
  schema-order fix (`PROMPT_EXPERIMENT_2026-08-03.md`'s v3), scoped to
  `reference_count<=1`, against case 3. Partial improvement only:
  `edits[0].subject` became correctly specific in 5/5, but
  `is_local_region`/`region` stayed wrong in 5/5 - same cross-field-
  consistency wall as the earlier 3-image regression. Not adopted (a
  half-fixed plan risks future code trusting `is_local_region` wrongly).
  See `tests/router/RESULTS_analyzer_field_reliability_v3.md`. Next
  candidate: a deterministic post-processor/validator (reject/re-request
  on subject-vs-is_local_region/region contradiction) instead of more
  wording - not started, needs its own decision. **Implemented as a
  diagnostic-only opt-in (2026-08-05):** `edit_plan_schema.py`'s
  `validate_edit_plan(check_consistency=True)` flags the inconsistency but
  is not wired into the router - the render path still doesn't consume
  `is_local_region`/`edits[]` at all, so a production reject/re-request
  gate would be premature (also awkward given ComfyUI graphs are DAGs with
  no native retry construct). See
  `tests/router/RESULTS_consistency_check.md`,
  `tests/router/test_consistency_check.py`. **Repeat-seed pass for cases 1/2
  (2026-08-05, analyzer-JSON-level, n=5, no render):** case 2 (global
  restyle) fully stable/correct 5/5; case 1's (local removal)
  `is_local_region` stable/correct 5/5, but its `edits[].subject`/`.region`
  placeholder-overuse is confirmed systematic (5/5), not an n=1 fluke -
  harmless for rendering (unconsumed fields), real analyzer-quality issue.
  See `tests/router/RESULTS_repeat_seed_cases12.md`. **Render-level pass
  also done (2026-08-05, n=3, full router incl. KSampler):** both cases
  fully stable/PASS across all 3 seeds, no variance. The "n=1 per case"
  backlog item is now closed for cases 1/2 (JSON-plan and render level
  both). Case 3 remains the only case with an unresolved visual failure.
  See `tests/router/RESULTS_repeat_seed_render_cases12.md`. **Two more
  untried candidates from `PROMPT_EXPERIMENT_2026-08-03.md` tested and
  rejected (2026-08-05):** `temperature=0` (n=1) reproduced the exact same
  failure as `temperature=0.1` - confirms a stable model mode, not
  sampling noise. Few-shot example + v3 schema (n=15, case 3):
  `edits[].subject`/`.region` fixed 15/15, but `is_local_region` only
  11/15 - and it REGRESSED on case 1 (5/5 -> 1/3) in a same-guidance
  regression check. No-go on adoption - `is_local_region` is
  prompt-sensitive/unstable across cases. Prompt/few-shot engineering for
  this field now considered exhausted; future use needs the diagnostic
  consistency validator, not more prompting. See
  `tests/router/RESULTS_analyzer_field_reliability_fewshot.md`.
  **Weighted reference-attention non-masking alternative tested and
  rejected (2026-08-05):** found `ComfyUI-Flux2Klein-Enhancer`'s
  `Flux2KleinRefLatentWeight` node is technically compatible with Qwen
  Image Edit 2511 (verified via `comfy/ldm/qwen_image/model.py`'s
  `attn1_patch`/`reference_image_num_tokens` hook, same one this node
  uses, despite its Flux2/Klein branding). Smoke test (weight sweep
  1.0/0.7/0.5/0.2 on `reference_index=1`=image2): scene tint shrank
  monotonically, but the dress never recolored in any variant - the
  mechanism controls reference-influence magnitude, not locality. All
  identified non-masking levers for case 3 (Qwen Image Edit path) are now
  exhausted; masking/region-conditioning is the only remaining
  mechanism-level lever. See `tests/router/RESULTS_ref_weight.md`.
  **Flux.2 Dev tested as an alternative model branch (2026-08-05, user
  priority: Flux.2 Dev before Klein):** n=3 full-conditioning pass (source
  + swatch via `ReferenceLatent`, color-naming prompt) - real locality
  win, no bleed, consistent. But a source-only ablation (same prompt) ALSO
  recolored the dress, and a decisive no-color-name test (swatch vs. no
  swatch, same seed) left the dress unchanged in BOTH variants -
  Flux.2 Dev did not pick up color from the image alone. Conclusion:
  strong text-driven local editing, but image-based reference transfer NOT
  demonstrated - the project's actual harder requirement. Closed out for
  this `ReferenceLatent` setup, not adopted. **Confirmed with a real
  photographic reference too (2026-08-05, from ComfyUI's input dir):**
  same no-color-name test, red leather jumpsuit product shot instead of
  the flat swatch - dress stayed black in both variants again, ruling out
  "bad test fixture." Fully closed out. Also found a separate VTON
  sub-project with 2+ months of closely related prior findings - see
  memory `project_vton_sibling_history`. **Swept all 4
  `reference_latents_method` variants too (2026-08-05), via the official
  `FluxKontextMultiReferenceLatentMethod` core node (no custom code):**
  `offset`/`index` both reproduce the black-dress negative unchanged;
  `index_timestep_zero` destroys image identity (different person/scene);
  `uxo/uno` collapses generation entirely. No chaining mode shows real
  image-reference transfer. Flux.2 Dev is out as an attention-bias-spike
  target - proceeding on Qwen instead, where reference consumption is
  already proven (`RESULTS_ref_weight.md`). See
  `tests/router/RESULTS_flux2dev_capability.md`.
- **SAM3-attention-hint spike, Stage 1 (logging-only) PASSED on Qwen
  (2026-08-05, user approved, no ComfyUI installation changes - custom
  nodes only):** new `custom_nodes/sam3_attn_probe/` package (dev repo,
  junction-linked into production, same pattern as
  `comfyui-qwenvl-structured-gguf`). `QwenBlockPatchLoggerProbe` uses the
  official `ModelPatcher.set_model_patch_replace()` API to register a
  `patches_replace["dit"][("double_block", i)]` hook - fires exactly as
  read from source: `total_blocks=60`, `img` already has source+both
  references concatenated, `reference_image_num_tokens` gives the source
  token range directly, cleaner than the originally-planned `attn1_patch`
  hook (img/txt still separate at block level). See
  `tests/router/RESULTS_sam3_spike_stage1.md`.
- **SAM3-attention-hint spike, Stage 2 (attention reimplementation, no
  bias) PASSED (2026-08-05):** `QwenBlockAttnReimplProbe` replaces one
  block's `attn.forward` (hand-copied from `Attention.forward`,
  ~60 lines) via `ModelPatcher.add_object_patch()` - reversible per-clone,
  not a permanent monkeypatch (confirmed `ModelPatcher.clone()` shares the
  underlying `nn.Module`, doesn't copy it). Baseline vs. patched render,
  same seed: pixel values bit-exact identical (numpy diff max=0). See
  `tests/router/RESULTS_sam3_spike_stage2.md`. Next: Stage 3 - real
  SAM3-mask-derived query-key bias at `optimized_attention_masked`'s
  `attn_mask` argument - not started.
- **Multi-reference routing implemented and VRAM-passed**
  (`tests/vram/router/RESULTS_RVref.md`): `build_router_graph.py`'s
  `build()` now accepts `refs: list[str]` (0-2 images), wiring them into
  the analyzer's `image2`/`image3` inputs, the schema's `reference_count`
  (via `image_director/edit_plan_schema.py`), and both
  `TextEncodeQwenImageEditPlus` nodes in the edit branch - same pattern as
  the non-router `combined-multiref` E2/E3 tests. Cold-floor VRAM: RVref2
  (1 reference) 532 MiB free, RVref3 (2 references) 916 MiB free, both
  n=1, both pass the 300 MiB floor. Lazy-switch correctness (unused branch
  never loads) confirmed to hold with references present. Back-to-back-
  without-`/free` sequencing measured twice (196/463 MiB free, see the
  hard rule above) - do not treat the isolated 916 MiB figure as
  representative of production back-to-back usage.
- The tested sequential Analyzer -> Editor path depends on
  `keep_model_loaded=false` on the analyzer node (its default is `true`);
  do not assume the tested VRAM-release behavior holds without that setting.
- Treat the combined Analyzer -> Editor path with two or three reference
  images as tested and initially found broken, then fixed
  (`tests/vram/combined-multiref/`, tests E2/E3 and their fixed re-runs):
  an independent-of-the-analyzer node (the negative-prompt
  `TextEncodeQwenImageEditPlus`) let ComfyUI's executor schedule the
  editor's CLIP load before/during the analyzer, causing near-OOM (as low
  as 27 MiB free). A `StringSubstring(analyzer_output, 0, 0)` node forcing
  a real dependency edge fixed it — validated with real margin (>=1192 MiB
  free) for both 2 and 3 references, but only from a clean/idle VRAM
  baseline reached via ComfyUI's `POST /free` endpoint. A warm baseline
  (unevicted resident models from a prior run) reintroduced a tight margin
  even with the fix applied — do not assume the fix alone guarantees
  headroom without also accounting for prior VRAM residency.
- More generally: when a graph mixes an analyzer/LLM node with several
  independent encoder/loader nodes, check whether any of those nodes truly
  depend on the analyzer's output before assuming ComfyUI will execute
  them in the intended sequential order — a missing dependency edge is
  enough to reintroduce VRAM overlap, and this will not show up as a
  node-level error, only as a tighter VRAM margin.

## MCP behavior

When invoked through Claude Code:

- use sandbox `read-only`
- use approval policy `never`
- use the supplied working directory
- remain within the current task's scope
- preserve the current thread context
- participate in substantive follow-up discussion
- respond directly to Claude's objections
- do not request permission to edit files
- do not expose credentials, secrets or unrelated personal files

If evidence is insufficient, state exactly what must be inspected or tested
next instead of guessing.
