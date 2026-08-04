# ComfyUI Image Director — Project Rules

## Source priority

Read the project sources in this order:

1. `docs/source/IMAGE_DIRECTOR_AUDIT.md`
2. `docs/source/COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`

When the documents conflict, the newer technical audit has priority.

Do not silently combine contradictory claims. Identify the conflict and use the
newer verified finding unless newer runtime evidence supersedes it.

## Project goal

Build a modular local Image Director for ComfyUI that converts natural-language
instructions and reference images into a structured plan and routes the task to
an appropriate generation or editing workflow.

Version 1 must remain small, inspectable, reproducible and reversible.

## Production environment

ComfyUI root:

`G:\ComfyUI-Easy-Install\ComfyUI`

Separate development repository:

`C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director`

The ComfyUI installation is a customized working environment.

Do not reorganize its existing folder structure.

Sibling dev repository providing the `QwenVLStructuredGGUF` custom node:

`C:\Users\Delcado\Documents\Software_Projects\comfyui-qwenvl-structured-gguf`

Installed into `G:\ComfyUI-Easy-Install\ComfyUI\custom_nodes\` via a
directory junction (that repo is the source of truth, not a copy). MIT,
not yet published to the Comfy Registry — do not publish it until the user
explicitly says it is feature-complete. Verify
`GET /object_info/QwenVLStructuredGGUF` before relying on it in a workflow
or test.

## Collaboration model

Claude and Codex are equal technical reasoning partners.

Both agents must:

- inspect the available evidence independently
- develop their own diagnosis and solution proposal
- identify assumptions, risks and missing evidence
- compare competing approaches
- challenge unsupported conclusions
- refine the solution through discussion
- distinguish consensus from unresolved disagreement

Neither agent should be treated as an unquestioned authority.

Claude coordinates the interaction because the user communicates through
Claude Code, but Claude must not reduce Codex to a one-way advisor or a final
rubber-stamp reviewer.

Codex must be given enough context to reason independently.

Claude should use follow-up calls in the same Codex MCP thread to discuss:

- differences between both analyses
- objections to proposed solutions
- alternative implementations
- evidence supporting each option
- testability and rollback
- unresolved technical uncertainty

The goal is a reasoned joint conclusion, not automatic agreement.

## Decision process

Before a meaningful implementation decision:

1. Claude inspects the relevant files and forms an initial analysis.
2. Codex independently inspects the same problem in read-only mode.
3. Claude compares both analyses.
4. Claude sends material differences, objections or open questions back to
   Codex using the same MCP thread.
5. Claude and Codex refine the options until:
   - they reach a supported consensus, or
   - the remaining disagreement is clearly documented.
6. Claude presents the resulting recommendation to the user, including:
   - the preferred solution
   - meaningful alternatives
   - supporting evidence
   - remaining disagreement
   - risks and required tests
7. The user approves consequential implementation changes.
8. Claude performs approved file modifications.

A disagreement must not be hidden merely to present a single answer.

When evidence cannot decide between alternatives, prefer a controlled test over
speculation.

## File modification authority

Claude Code is the only agent permitted to modify:

- files in the development repository
- approved ComfyUI workflow files
- approved ComfyUI configuration or code

Codex remains read-only when invoked through Claude Code.

This restriction concerns file operations only. It does not make Codex
subordinate in architectural or technical decision-making.

Codex may propose concrete changes, algorithms, structures and complete
solutions, but Claude must evaluate and implement them.

## Current architecture status

The intended minimal architecture is:

1. Instruction and source/reference images
2. Standalone image analyzer
3. Structured JSON edit plan
4. Generation or editing branch

Current candidate execution branches:

- Generation: Z-Image Turbo
- Image editing: Qwen Image Edit 2511 (replaced Qwen Image Edit 2509,
  2026-08-03, user's explicit decision - not an A/B, a full swap). UNet
  `models\unet\Qwen Image Edit 2511\qwen-image-edit-2511-Q4_K_M.gguf`
  downloaded from `unsloth/Qwen-Image-Edit-2511-GGUF` on HuggingFace
  (Apache-2.0, built for `ComfyUI-GGUF` by city96 - the loader already
  installed and used for 2509), byte-size-verified against HuggingFace's
  reported Content-Length (13,244,758,624 bytes) and GGUF-magic-verified.
  **Runtime-smoke-tested 2026-08-03, succeeded**: standalone editor graph
  (`UnetLoaderGGUF` 2511 + `CLIPLoaderGGUF` on the new abliterated encoder,
  see below + existing `qwen_image_vae.safetensors`, `FluxKontextImageScale`
  -> `CFGNorm` -> `ModelSamplingAuraFlow` -> `TextEncodeQwenImageEditPlus`
  x2 -> `KSampler` -> `VAEDecode` -> `SaveImage`, one reference image,
  instruction "remove the blue square, keep everything else unchanged")
  completed with `execution_success`, and the output image was visually
  inspected (not pixel/mask-diffed): the blue square appeared correctly
  removed while the red circle and background appeared preserved. At the
  time of this note (2026-08-03), this model pair had not yet been re-run
  through the full Test C analyzer+editor combined path or the E2/E3
  multi-reference VRAM tests - only this standalone single-reference
  editor smoke test was confirmed; the router built the next day supersedes
  this with its own multi-reference VRAM passes (`RESULTS_RVref.md`,
  `RESULTS_RVrefchain.md`) using this same model pair. The old 2509 UNet
  (`Qwen-Image-Edit-2509-Q4_K_M.gguf`) was deleted; its `.metadata.json`/
  `.jpeg` were kept for provenance. Production workflows that hardcoded the
  old UNet filename (`Qwen Image Edit - VTON v13/v14/v15.json`,
  `QWEN_IMAGE_EDIT_WORKFLOW.json`) will fail to load it until their
  `UnetLoaderGGUF` widget value is manually updated to
  `Qwen Image Edit 2511\qwen-image-edit-2511-Q4_K_M.gguf` (and their
  `CLIPLoaderGGUF` value to the new encoder path below) - the user opted to
  do this themselves when next touching those workflows, not as part of
  this change.
- FLUX.2: outside the Version-1 critical path until separately measured.
  Informal candidate note (2026-08-03): user-supplied chat images from a
  single uncontrolled img2img run reportedly using an existing production
  workflow (`G:\ComfyUI-Easy-Install\ComfyUI\user\default\workflows\Flux.2
  Dev\TooReal Studio - Flux2 Dev NVFP4 img2img.json`) appeared to preserve
  identity, pose, and armor detail while producing a photorealistic restyle
  from a game-screenshot source image. Workflow JSON independently
  inspected and confirmed: `UNETLoader` -> `flux2-dev-nvfp4-mixed.safetensors`,
  `CLIPLoader` -> `mistral_3_small_flux2_fp4_mixed.safetensors` (type
  `flux2`), `VAELoader` -> `flux2-vae.safetensors`; source image VAE-encoded
  and injected via `ReferenceLatent` into both positive and negative
  conditioning (cfg 1.2, 28 steps, dpmpp_sde); no dedicated identity-lock
  node (no IPAdapter/InstantID-style mechanism) — the graph's apparent
  preservation mechanisms are prompt instructions plus the reinjected
  source latent. This remains anecdotal (n=1, no A/B test, no VRAM/timing
  data, not run through the Image Director Analyzer -> Editor path, and the
  workflow was not re-executed by Claude/Codex to reproduce the result) and
  does not change FLUX.2's critical-path status; it is a reason to
  prioritize a controlled FLUX.2 measurement later.

The standalone analyzer loader and minimal inference path are smoke-tested.
`AILab_QwenVL_GGUF_Advanced` can load the installed Qwen2.5-VL-7B GGUF pair
(the same files Qwen Image Edit uses as its own text encoder) as an
independent analyzer, via a `gguf_models.json` catalog entry plus two file
hardlinks — no new download, no file copy. See
`docs/source/IMAGE_DIRECTOR_AUDIT.md` §13.

Analyzer-only Test A and the sequential Analyzer -> Editor Test C (one
graph, one queue press, one reference image) both succeeded. Do not
describe Test A or Test C as blocked.

**Text encoder swapped 2026-08-03 - Test A/C's smoke-test evidence no
longer reflects the currently installed weights.** The shared Qwen2.5-VL-7B
GGUF pair (used by both the analyzer and Qwen Image Edit's own CLIP) was
replaced with an uncensored/"abliterated" variant, user's explicit request:
`Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf` +
`Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf`, from
`mradermacher/Qwen2.5-VL-7B-Instruct-abliterated-GGUF` on HuggingFace (a
GGUF quantization of `huihui-ai/Qwen2.5-VL-7B-Instruct-abliterated`),
byte-size- and GGUF-magic-verified. `Q4_K_M` chosen over the previously
installed `Q4_K_S` (a step up in quality) per the user's explicit request;
a further step to `Q5_K_S` was discussed as a fallback if `Q4_K_M` turns
out insufficient, not yet needed. The old, non-abliterated pair
(`Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf` + `-mmproj-BF16.gguf`) was deleted
at both hardlink locations (`text_encoders\Qwen Image Edit 2509\` and the
analyzer's `llm\GGUF\Qwen\Qwen2.5-VL-7B-Instruct-GGUF\` catalog target).
The `gguf_models.json` catalog entry was renamed/repointed to
`Qwen2.5-VL-7B-Instruct-abliterated-GGUF` (author `huihui-ai`), hardlinked
into `llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\`. The new
`CLIPLoaderGGUF` widget value for any workflow (production or test) is
`Qwen2.5-VL-7B-abliterated\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf`
(type `qwen_image`); the mmproj file lives alongside it in the same folder
as `Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf` (not separately
selected in `CLIPLoaderGGUF` - `AILab_QwenVL_GGUF_Advanced` picks up the
mmproj via the `gguf_models.json` catalog entry, not a workflow widget).

**Open, not evaluated: refusal/content-moderation behavior changed.**
Abliteration specifically targets refusal behavior - the analyzer may now
describe or the editor may now condition on content the previous model
would have declined. This was not evaluated today; the smoke tests only
checked that vision/edit *capability* still works, not what content
boundaries changed. Do not infer anything about plan quality, safety
behavior, or output appropriateness from these smoke tests - track this as
a genuinely new, separate variable if it becomes relevant later.

**Runtime-smoke-tested 2026-08-03, succeeded, both roles:** as the
standalone analyzer (`AILab_QwenVL_GGUF_Advanced`, model_name
`Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf`, one reference image, the
same red-circle/blue-square synthetic test image used throughout this
project's testing) correctly described "a red circle and blue square on a
light gray background" - vision capability intact after
abliteration+quantization. As Qwen Image Edit 2511's own CLIP (see the UNet
entry above) - correctly conditioned a real edit (removed the blue square,
preserved the rest). Do not assume Test A/C's or E2/E3's *structural VRAM
margin numbers* transfer without re-running those specific tests (file
sizes changed: new UNet ~13.24GB vs old ~13.07GB, new CLIP ~4.36GB vs old
~4.46GB - close but not identical, and the tight ~1.2-1.3GiB VRAM margin
found in the fixed E2/E3 multi-reference tests has not been re-measured
with these files). Same VRAM-release caveat applies
(`keep_model_loaded=false`). Production workflows that hardcoded the old
CLIP filename (`Qwen Image Edit - VTON v10-v15.json`,
`QWEN_IMAGE_EDIT_WORKFLOW.json`) will fail to load it until their
`CLIPLoaderGGUF` widget value is manually updated - the user opted to do
this themselves when next touching those workflows.

**Test script paths are now stale.** Every `MODEL_PATH`/`MMPROJ_PATH`
constant in this project's own test scripts
(`tests/vram/combined-multiref/`, `tests/schema/analyzer-json/`,
`tests/schema/analyzer-json-structured/`) and the sibling
`comfyui-qwenvl-structured-gguf` repo's probes still point at the deleted
`Qwen Image Edit 2509\...`/`Qwen2.5-VL-7B-Instruct-GGUF\...` files. Historic
run outputs under those directories remain valid records of what was true
when they ran - do not edit them. Re-running any of those scripts as-is
will fail (file not found) until their path constants are updated to the
new UNet/CLIP locations.

VRAM was released back to idle after the analyzer step only because
`keep_model_loaded=false` was set explicitly on the analyzer node; its
default is `true`. Any reusable Image Director workflow must set
`keep_model_loaded=false` for the tested sequential path's VRAM behavior to
hold.

What remains unresolved is the productive Image Director logic, not the
analyzer loader itself:

- analyzer prompt design and plan quality. A scoped experiment
  (`tests/schema/analyzer-json-structured/PROMPT_EXPERIMENT_2026-08-03.md`,
  not adopted, baseline unchanged) found that simple wording fixes appeared
  to fix single-edit content problems (edits-vs-preserve confusion, `"*"`
  placeholders) in paired reruns (not a reliability screen), but multi-edit
  composition and `user_instruction`/`prompt`/`edits` cross-field
  consistency were not reliably fixed by prompt wording alone at n=1-2
  samples per variant - don't re-attempt the same wording-only approach
  without reading that file first
- router-side semantic validation, including checking that every
  `reference_slots` value actually names an image key present in that same
  response's `images` object (JSON Schema cannot express this cross-field
  constraint by itself - see the "Structured JSON edit-plan output" section
  below)
- availability-specific schema selection/generation as actual router logic
  - DONE. `tests/router/build_router_graph.py`'s `build()` now calls
  `image_director/edit_plan_schema.py`'s `edit_plan_schema()` with
  `reference_count=len(refs)` picked from the images actually supplied at
  graph-build time; see the "Multi-reference routing implemented" note
  above and `tests/vram/router/RESULTS_RVref.md`.
- the task router's routing *mechanism* is now built and smoke-tested (see
  "V1 task router" section below) - what's still missing: a repeat-seed
  reliability pass (the multi-reference back-to-back VRAM margin is now
  measured twice, 196/463 MiB free - see the mandatory safety rules below),
  and any plan/content-quality guarantee
- visual acceptance tests on real photos - a first n=1x3 look is done (see
  "Plan/content quality on a real photo" below,
  `tests/router/RESULTS_content_quality.md`) - local edit and global
  restyle passed both structurally and visually; a multi-reference color
  transfer failed visually despite a reasonable consumed prompt. Not a
  reliability screen - one photo, one seed per case.

Do not infer routing correctness or image quality from the loader/runtime
smoke tests alone. See below: structural JSON reliability is now solved;
plan/content quality is not.

### Plan/content quality on a real photo — first look, not a reliability screen

`tests/router/RESULTS_content_quality.md`: 3 cases on a real photo (local
object removal, global restyle, multi-reference color match), each n=1.
Local removal and global restyle passed both the structured plan and the
visual output. The multi-reference case's plan had multiple issues
(`is_local_region` likely wrong, `images.image2.role: "source"` - a real
schema gap, see below - and the recurring `"entire image"`/`"full image"`
placeholder overuse already documented on synthetic images) and its
*visual* output also failed (the whole image got tinted, not just the
targeted garment) - but per Codex's review, the wrong structured fields
cannot be asserted as the cause, since the current router only consumes
`task`/`prompt` from the plan; `edits[]`/`preserve[]`/`images[].role` are
generated but never read downstream. Case 1 is the proof this separation
is real: its `edits[]` was wrong too, but its visual result was correct,
because the actually-consumed `prompt` field was accurate.

**Schema gap fixed (same session):** reference image slots (`image2`/
`image3`) could legally have `role: "source"` -
`image_director/edit_plan_schema.py`'s `_IMAGE_SLOT` role enum was not
narrowed to exclude `"source"` for non-`image1` slots, so a semantically
wrong plan passed both grammar constraint and `validate_edit_plan()`.
Fixed: added `REFERENCE_ROLE_ENUM_ORDERED` (the full role list minus
`"source"`), used it for `_IMAGE_SLOT`, and `validate_edit_plan()` now
checks `image1`'s role against `== "source"` specifically and every other
slot against the narrower enum. Self-tested (schema/validator reject the
old bug, accept correct plans, all 5 previously-saved
`analyzer-json-structured` outputs still validate clean). Re-testing case
3 live confirmed `image2.role` is now `"object_reference"`, not
`"source"`. The re-test's visual output also happened to be correct this
time, but that should NOT be attributed to this fix - the render path
still doesn't consume `images[].role` at all; see
`tests/router/RESULTS_content_quality.md`'s "Update" section for the more
likely explanation (prompt wording variance between the two analyzer
samples).

**"background"-word hypothesis isolated and confirmed (A/B test):** the
prompt-wording explanation above was later isolated in a standalone
analyzer-bypassing A/B test (same seed/images, only the prompt's
"background" clause varied) - confirmed causal for this image/prompt pair:
"a solid blue background" -> whole-image tint (reproduces the original
failure); "a solid blue" -> correct dress-only recolor. Not proven to
generalize beyond this case. **Follow-up guidance-clause fix attempted and
failed:** adding an instruction to `GUIDANCE` telling the analyzer to avoid
"background"/"backdrop" wording did not suppress the word at n=1, and the
re-tested visual output was still wrong (differently - a background color
patch instead of a full tint, dress still unchanged). Reverted, not
adopted. See `tests/router/RESULTS_ab_background_word.md`.

### Structured JSON edit-plan output — schema exists, structural reliability solved via an external node

The structured edit-plan schema is defined: `docs/schema/edit_plan.schema.json`
(canonical, human-readable - `task: "generate"|"edit"`, `is_local_region`,
`images.image1/2/3` with `role`, `edits[]`, `preserve[]`) and
`docs/schema/edit_plan.grammar.schema.json` (the same contract restructured
as `oneOf` of two flat branches, because llama-cpp-python's JSON-Schema-to-
grammar converter does not support `if`/`then` conditionals - confirmed by
reading `llama_grammar.py`'s `SchemaConverter.visit`, not assumed).

Prompt-only structured output (`AILab_QwenVL_GGUF_Advanced`, no grammar
constraint, schema explained in the prompt text) was tested and failed:
`tests/schema/analyzer-json/` scored 0/3 (task=generate case even put the
`images.image1` example object into the `prompt` field; task=edit cases had
empty `images`, empty strings, or an unrequested `reference_slots`). Do not
use prompt-only structured output as the analyzer's structured-plan path.

This led to a new, separate MIT-licensed dev repo,
`comfyui-qwenvl-structured-gguf`
(`C:\Users\Delcado\Documents\Software_Projects\comfyui-qwenvl-structured-gguf`,
not derived from the GPL-3.0 `ComfyUI-QwenVL`/`ComfyUI-QwenVL-Mod`, since
this project's other published node packages are all MIT under the
`delcado` Comfy Registry publisher and copyleft-derived code would conflict
with that), providing `QwenVLStructuredGGUF`: same GGUF/llama-cpp-python
loading approach, but wires `response_format={"type": "json_object",
"schema": ...}` into `create_chat_completion`, grammar-constraining the
model's output to a caller-supplied JSON Schema. **Not yet published to the
Comfy Registry** - the user's explicit instruction is not to publish until
the node is feature-complete. It is installed into the production ComfyUI
via a directory junction (`custom_nodes\comfyui-qwenvl-structured-gguf` ->
the dev repo), not a copy. Verify `GET /object_info/QwenVLStructuredGGUF`
before relying on it in any workflow or test - it is not a permanent,
well-known dependency the way core or registry-published nodes are.

**Validated, structural reliability only:** across the node repo's own
probes (single image, then multi-image `image`/`image2`/`image3` with a
documented positional/contiguous-slot contract) and this project's own
first-party test (`tests/schema/analyzer-json-structured/`, 4 cases:
generate / local edit / global edit / 2-reference edit, all through the
real ComfyUI queue), every response was valid, schema-conformant JSON - no
markdown fences, no missing/extra keys, no wrong types. Use
`QwenVLStructuredGGUF` with an availability-specific schema (only allow
`images`/`reference_slots` shapes that match the images actually wired into
that call) - not one shared, maximally-permissive schema - since a
too-permissive schema previously let the model hallucinate a
`reference_slots` reference to an image that was never provided.

**Not validated - plan/content quality remains open:** `is_local_region`
has been observed both correct and flipped across otherwise-identical
structural passes (sampling variance, not a schema problem).
`tests/schema/analyzer-json-structured/RESULTS.md` documents further
content issues found in a passing run: spurious `edits[]` entries for
things that should stay unchanged, `"*"` placeholder subject/region values,
garbled prompt text, and at least one spatially wrong region description.
Grammar constraint guarantees *shape*, never *content*. Do not infer plan
quality, routing correctness, or image quality from a structural pass.

### Combined Analyzer -> Editor with 2-3 reference images — tested, found broken, fixed

The one-reference-image case (Test C) does not generalize by itself. A
combined VRAM smoke test with 2 and 3 reference images
(`tests/vram/combined-multiref/`, tests E2/E3) found a real scheduling
defect: the editor's negative-prompt `TextEncodeQwenImageEditPlus` node has
no data dependency on the analyzer, so ComfyUI's executor can schedule it —
and load the editor's own CLIP — before or during the analyzer's run. This
is not a cleanup problem (`keep_model_loaded=false` still worked); it is a
graph-topology problem: an independent node lets the two phases overlap
instead of staying sequential. Effect: E2 completed with only 112 MiB free
VRAM at peak, E3 with only 27 MiB — both far under any safe margin, though
neither actually crashed.

**Fix, tested and validated:** insert a `StringSubstring` node between the
analyzer's `STRING` output and the negative prompt input
(`string=[analyzer_output], start=0, end=0`) — `string[0:0]` is always
`""` (plain Python slicing, confirmed via `comfy_extras/nodes_string.py`
source), so the negative prompt is unaffected, but the negative-prompt
node now has a real dependency on the analyzer and cannot be scheduled
before it. From a clean/idle VRAM baseline, this fix restores full
non-overlapping sequential execution and passes with real margin for both
2 references (1192 MiB free at peak) and 3 references (1303 MiB free at
peak, zero samples under 300 MiB across the whole run).

**Still open:** a warm VRAM baseline (leftover resident models from a
prior run, not evicted) reintroduces a tight margin even with the fix
applied (123 MiB free in one warm-baseline run) — this is a separate risk
from the scheduling defect. ComfyUI's built-in `POST /free {"unload_models": true, "free_memory":
true}` endpoint produced a clean baseline in the fixed cold reruns and is
the validated preflight for this test setup — not a universal guarantee
for every possible custom-node or foreign (e.g. llama.cpp) allocation.
Whether a production Image Director workflow needs a `/free` preflight (or
some other warm-cache policy) on every run is not decided. This fix was validated only as an
ad-hoc API-format test graph, not as an actual saved workflow file, and
only for infrastructure/VRAM behavior — no image-quality, identity, or
edit-locality claim is supported by these tests.

### V1 task router — routing mechanism validated end-to-end, scope-limited

Full writeup: `tests/router/RESULTS_router_v1.md`, `tests/router/RESULTS_lazy_switch.md`.
Graph builder: `tests/router/build_router_graph.py`.

**Mechanism validated.** One graph, one queue press: `QwenVLStructuredGGUF`
(analyzer, grammar-constrained JSON) emits `task`, extracted via
`GetTextFromJson` and compared with `easy compare`, feeding `easy ifElse`'s
`boolean` to lazily select exactly one of two fully-built, expensive
branches - Z-Image Turbo (generate) or Qwen Image Edit 2511 (edit) - to a
single final `SaveImage`. `easy ifElse`'s lazy evaluation was first proven
in isolation with cheap stand-ins
(`tests/router/RESULTS_lazy_switch.md`: the unused branch's entire upstream
chain, including a multi-second model load, is never scheduled, confirmed
both from `comfy_execution/graph.py` source and empirically, both switch
directions). Then proven with the real branches
(`tests/router/RESULTS_router_v1.md`): a generate instruction ran only
Z-Image Turbo's components (log showed `ZImageTEModel_`/`Lumina2`/
`AutoencodingEngine`, no Qwen Image Edit lines) and produced an image
visually matching the instruction; an edit instruction ran only Qwen Image
Edit 2511's components (log showed `QwenImageTEModel_`/`QwenImage`, no
Z-Image Turbo lines) and produced an image with exactly the requested
change applied, everything else visually unchanged. n=1 per direction -
documented and Codex-reviewed as adequate to close the *mechanism*
milestone, explicitly not a reliability characterization.

**A real mistake surfaced and fixed in the process:** the first submission
used the official ComfyUI Z-Image Turbo template's file names
(`z_image_turbo_bf16.safetensors`, `qwen_3_4b.safetensors`) without
verifying they were installed - they were not. `POST /prompt` returned a
`prompt_id` with HTTP 200 (no exception), but the response body's
`node_errors` field held a "Value not in list" validation error, and
`/history` showed `status_str: success` with empty `outputs: {}` - a
silent failure that checking only HTTP status would miss entirely. Fixed
in `tests/router/submit_and_check.py`: raises on `node_errors` at submit
time, and (per Codex review) also now hard-fails if the run didn't
complete, any `[ERROR]` line appeared in the log during the run, or no
image output was produced - checking `node_errors` alone still left room
to misread a later empty/errored result as a pass. The same missing-check
pattern existed in `tests/schema/analyzer-json*/submit_and_capture.py` and
`tests/vram/combined-multiref/submit_and_monitor.py` - those runs' saved
evidence was not invalidated (cross-checked another way at the time).
Fixed: the `node_errors`-checking `submit()`/`poll_history()` HTTP layer is
now consolidated in `tests/lib/comfy_submit.py`, imported by all four
ComfyUI-submitting test scripts in this project, so any future test script
gets the guard by construction instead of needing its own copy.

**VRAM margins, now measured (`tests/vram/router/RESULTS_RV.md`):** the
router graph's own VRAM behavior was re-measured with the actual router
graph (not a stand-in), fresh `/free`-forced cold floor before each run,
250ms `nvidia-smi` sampling throughout, and `execution_cached.nodes: []`
confirming genuine fresh execution (not a node-output cache hit) for both
directions. Both show the same two-plateau-with-trough shape as Test
C/E2/E3's non-router path: analyzer loads, peaks, and fully releases
*before* the selected branch begins loading - no sampled overlap in either
direction. RV-generate (Z-Image Turbo): worst sampled margin 2391 MiB free,
a single ~250ms spike, comfortable. **RV-edit (Qwen Image Edit 2511): worst
sampled margin 954 MiB free, sustained for ~37s** - still above this
project's 300 MiB pass threshold, but the tightest margin recorded for any
passing VRAM test in this project, and tighter than E2/E3's own *2-3
reference* margins (1192/1303 MiB free) despite being only 1 reference
image here - most likely the current 2511 + abliterated-encoder pair
having a larger combined footprint than E2/E3's older 2509 + standard-
encoder pair (exact contributor not isolated). Per Codex review: **this is
now the real binding constraint** - at the time of this test, multi-
reference edit routing had not been measured; it has since been
measured both cold-floor (see "Multi-reference routing implemented"
above, `RESULTS_RVref.md`) and back-to-back without `/free` (196/463 MiB
free, see "Multi-reference routing implemented" and the mandatory safety
rules below, `RESULTS_RVrefchain.md`). Also newly observed: neither
branch's models are released after the run completes (both settle to a
resident plateau, not back to idle).

**Back-to-back requests without `/free`, characterized and found unsafe as
a default policy (`tests/vram/router/RESULTS_RVchain.md`):** running
RV-generate then immediately RV-edit with no `/free` in between completed
successfully at n=1, but hit **901 MiB free at its worst sampled point -
the tightest margin recorded in this project's history** - during the
*analyzer's* own load stacking on top of the still-fully-resident previous
branch, not during either diffusion branch's sampling. Root cause,
confirmed by Codex before the test and reproduced by it:
`QwenVLStructuredGGUF` loads its GGUF model directly via
`llama_cpp.Llama(...)` (`comfyui-qwenvl-structured-gguf`'s
`nodes/structured_gguf_vl.py:78-102`), outside ComfyUI's
`comfy.model_management` - so it cannot trigger eviction of stale resident
models itself. Eviction only happened a few seconds later, once the edit
branch's own `VAELoader` (a ComfyUI-managed node) requested memory and
comfy's own eviction logic reacted to *that* request - the analyzer's own
load remained safe only until that happened, not because of anything that
proactively made room for it. See the mandatory safety rule below - this
is treated as a hard "do not do this in production yet" rule, not just a
documented open concern, per Codex's explicit recommendation.

**Analyzer-load gap fixed, but a second, tighter margin found in its
place (`tests/vram/router/RESULTS_RVfix.md`):** `QwenVLStructuredGGUF` got
an opt-in `free_vram_before_load: BOOLEAN` (default `False`) that calls
`comfy.model_management.unload_all_models()` + `soft_empty_cache()` right
before loading a genuinely new model. Set `True` only in the router
graph's analyzer node (`tests/router/build_router_graph.py`). Repeating
the exact RVchain back-to-back-no-`/free` scenario with the fix twice
(n=2, fresh seeds each time) confirms it works: VRAM used drops sharply
(e.g. 11555 -> 2051 MiB) immediately before the analyzer's `Llama(...)`
load in both runs - the analyzer no longer stacks on resident weights, and
the original 901 MiB near-miss location does not recur. **But both runs'
overall worst sampled margin moved elsewhere and got tighter: 271 MiB free
(run 1) and 238 MiB free (run 2), both during Qwen Image Edit 2511's own
diffusion load/`KSampler` phase** (log-confirmed `full load: True`, no
OOM, no errors, correct output both times). Reproducible at n=2, both
below the project's 300 MiB floor - not attributed to noise. Root cause
not isolated (could be `QwenImage`'s own footprint, allocator state after
the back-to-back sequence, fragmentation, or residual residency from the
analyzer's eviction call - Codex was explicit that this is not proven
independent of the fix, only that the fix's own target - the analyzer load
- is confirmed no longer the tight point). See the updated mandatory
safety rules below.

**Isolation follow-up:** an edit-only request submitted alone (no
preceding generate/analyzer request, fresh `/free`) measured **456 MiB
free** - confirming the back-to-back sequence itself costs roughly 200 MiB
of margin versus an isolated request (n=1 on the isolated side, per Codex
enough to document but not to generalize the exact magnitude). Also
flags a separate, unexplained ~500 MiB gap between this isolated result
(456 MiB) and the original `RESULTS_RV.md` clean-edit measurement (954
MiB) - that older figure should no longer be treated as a stable
baseline. See `tests/vram/router/RESULTS_RVfix.md` for full detail.

**Multi-reference routing implemented and VRAM-passed
(`tests/vram/router/RESULTS_RVref.md`):** `tests/router/build_router_graph.py`'s
`build()` now accepts `refs: list[str]` (0-2 images), wiring them into the
analyzer's `image2`/`image3` inputs, the schema's `reference_count`, and
both `TextEncodeQwenImageEditPlus` nodes in the edit branch - closing the
availability-specific schema selection gap below. Cold-floor VRAM pass:
RVref2 (1 reference) 532 MiB free, RVref3 (2 references) 916 MiB free -
both pass the 300 MiB floor, both n=1. Lazy-switch correctness
(unused branch never loads) confirmed to hold with references present.
Back-to-back-without-`/free` sequencing measured twice for the 2-reference
case (`RESULTS_RVrefchain.md`): **196 MiB free (run 1), 463 MiB free
(run 2)** - 196 MiB is the tightest margin recorded in this project, and
the spread between the two runs is itself evidence this scenario isn't
safe to call stable - see the mandatory safety rules below. Do not treat
the isolated 916 MiB figure above as representative of production
back-to-back usage.

**Not settled by this milestone:**
- the analyzer-load gap itself is fixed (see above,
  `RESULTS_RVfix.md`) - but the edit branch's own tight margin that
  replaced it (271/238 MiB free, n=2) has no code-level fix proposed. The
  isolation test Codex suggested has been run: an edit-only request (no
  preceding generate request) still measured only 456 MiB free - tighter
  than the original `RESULTS_RV.md` clean-edit figure (954 MiB, no longer
  a stable baseline) and itself not a wide margin. Per Codex's read (this
  session), the edit branch is ComfyUI-managed and already full-loads
  successfully - the constraint looks like Qwen Image Edit 2511's genuine
  VRAM footprint being close to this 16 GB card's ceiling under this
  graph/session shape, not a fixable eviction defect the way the analyzer
  gap was. **`--reserve-vram 2.5` validated as a working mitigation**
  (`tests/vram/router/RESULTS_reservevram.md`): moves the worst tested
  back-to-back margin (multi-reference, no `/free`) from 196 MiB to 2410
  MiB by forcing `QwenImage`'s UNet into partial/streamed loading instead
  of full residency - at a real cost (~1.5-2x slower on the tested
  request). Not adopted as the default launch config - ComfyUI was
  restored to standard immediately after the n=1 test. **User decision
  (2026-08-04): do not run `--reserve-vram` permanently** - the speed cost
  isn't worth it project-wide. The mandatory `/free`-between-requests rule
  below is the settled default operational answer, not just a fallback;
  `--reserve-vram` stays documented as a verified-working alternative
  lever if VRAM pressure ever forces the question again, but it is not the
  plan.
- plan/content quality - a first n=1x3 real-photo look is done (see
  "Plan/content quality on a real photo" above,
  `tests/router/RESULTS_content_quality.md`): local edit and global
  restyle passed, a multi-reference color transfer failed visually. Not a
  reliability screen - one photo, one seed per case. Root cause of that
  failure is now explained (the analyzer's "background" wording, isolated
  via a standalone A/B test - `tests/router/RESULTS_ab_background_word.md`)
  but not fixed at the analyzer-prompting level, and not confirmed to
  generalize beyond this one image/prompt pair.
- the Z-Image Turbo checkpoint/text-encoder pair used here
  (`jibMixZIT_v10.safetensors` + `Lockout-Qwen3-4b-zimage-hereticV2-q8.gguf`,
  both user-chosen) was not benchmarked against the other checkpoint/CLIP
  options sitting on disk

## Mandatory safety rules

- The analyzer-load/eviction gap (`RESULTS_RVchain.md`'s 901 MiB near-miss)
  is fixed when the router graph's analyzer node has
  `free_vram_before_load=True` set (it is, in
  `tests/router/build_router_graph.py`) - do not remove that flag from the
  router graph without re-measuring.
- Do not use the V1 task router for repeated back-to-back production
  requests without calling `POST /free {"unload_models": true,
  "free_memory": true}` between requests, even with the analyzer fix
  applied - a *different* margin (the edit branch's own diffusion
  load/`KSampler` phase) was measured at 271/238 MiB free (n=2,
  `tests/vram/router/RESULTS_RVfix.md`), below the project's 300 MiB
  floor, in the exact same back-to-back-without-`/free` scenario. This
  rule stays in force until that margin has a mitigation or a
  wider-margin repeated-use test passes. **This is especially strict for
  multi-reference edit routing:** `tests/vram/router/RESULTS_RVrefchain.md`
  measured a 2-reference generate -> edit sequence twice - **196 MiB free
  (run 1), 463 MiB free (run 2)** - the worse of which is the tightest
  margin recorded in this project, sustained for ~27.5s under 400 MiB
  during the edit branch's own full-load/`KSampler` phase. The spread
  between the two runs is itself part of the evidence: this scenario is
  not stable enough to call safe without `/free`.
- Do not modify ComfyUI files unless the current user-approved task requires it.
- Do not install or download models, nodes or dependencies without explicit
  user approval.
- Do not pull, reset, rebase, clean or overwrite dirty custom-node repositories.
- Do not invent node classes, model paths, ports, APIs or command-line options.
- Verify installed node classes and concrete model paths before using them.
- Preserve existing working workflow sections.
- Create a backup before modifying an existing workflow.
- Validate complete workflow JSON after every workflow edit.
- Restart ComfyUI after installing or changing custom-node code before judging
  a workflow created in the GUI.
- Do not change global ComfyUI configuration unless strictly necessary and
  explicitly approved.
- Do not create commits or push changes without explicit user approval.

## Development method

Work in small, testable steps.

For every implementation step:

1. Inspect the relevant files and current state.
2. Complete the joint Claude-Codex decision process.
3. State the exact scope of the proposed change.
4. Identify files that would be modified.
5. Explain the expected result and the test.
6. Obtain user approval where required.
7. Let Claude change only one logically related part.
8. Run all locally possible validation.
9. Request the user's real ComfyUI runtime test when local validation is not
   sufficient.
10. Let Claude and Codex jointly evaluate the resulting evidence.
11. Review the complete diff.
12. Record unresolved risks honestly.

Do not bundle unrelated fixes.

## Evidence rules

Distinguish clearly between:

- verified installation facts
- findings from source-code inspection
- live runtime test results
- historical results from older hardware
- assumptions requiring a new test
- conclusions agreed by both agents
- unresolved disagreement between the agents

File or node presence is not proof of runtime compatibility.

Disk size is not proof of simultaneous VRAM usage.

Do not claim visual quality, identity preservation or edit locality without an
actual controlled image test.

Consensus between Claude and Codex is not evidence by itself. Their conclusion
must remain grounded in files, source code, logs, documentation or tests.

## Workflow requirements

- Prefer existing native ComfyUI nodes and already-installed custom nodes.
- Use only confirmed node classes.
- Provide complete workflow JSON files rather than isolated patch fragments.
- Keep model loading and text-encoder loading separately switchable where the
  workflow requires it.
- Keep GGUF and safetensors loader paths separate.
- Do not add fallback paths for SageAttention unless the user explicitly asks.
- Expose routing decisions and the structured edit plan visibly.
- Preserve sufficient metadata for reproducibility.
- Do not make the router a black box.

## Testing requirements

Use controlled A/B tests.

Keep all unrelated variables constant and change only one variable at a time.

Relevant evaluation categories include:

- identity preservation
- instruction compliance
- edit locality
- non-target preservation
- material realism
- lighting consistency
- anatomy
- background preservation
- VRAM behavior
- execution time
- reproducibility

When Claude and Codex prefer different technically plausible solutions, design
the smallest controlled comparison that can resolve the disagreement.

## Communication

Normal discussion may be in German.

Technical project documentation and persistent project files should be written
in English unless the user explicitly requests otherwise.

Prefer complete copy-and-paste-ready files and commands.

Report failures and uncertainty directly. Do not hide incomplete validation,
agent disagreement or unsupported assumptions.
