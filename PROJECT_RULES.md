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
- Image editing: Qwen Image Edit 2509
- Qwen Image Edit 2511: future A/B candidate
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

VRAM was released back to idle after the analyzer step only because
`keep_model_loaded=false` was set explicitly on the analyzer node; its
default is `true`. Any reusable Image Director workflow must set
`keep_model_loaded=false` for the tested sequential path's VRAM behavior to
hold.

What remains unresolved is the productive Image Director logic, not the
analyzer loader itself:

- analyzer prompt design and plan quality
- router-side semantic validation, including checking that every
  `reference_slots` value actually names an image key present in that same
  response's `images` object (JSON Schema cannot express this cross-field
  constraint by itself - see the "Structured JSON edit-plan output" section
  below)
- availability-specific schema selection/generation as actual router logic
  (the first-party test, `tests/schema/analyzer-json-structured/`, narrows
  the `response_format` schema per case by hand in `build_graph.py`; a real
  router still needs to build the right schema variant at runtime from
  however many reference images were actually supplied)
- the task router
- visual acceptance tests (identity preservation, edit locality, instruction
  compliance) on real photos

Do not infer routing correctness or image quality from the loader/runtime
smoke tests alone. See below: structural JSON reliability is now solved;
plan/content quality is not.

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

## Mandatory safety rules

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
