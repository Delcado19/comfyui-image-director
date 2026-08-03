# V1 task router - first end-to-end result

**Both routing directions PASS**, verified via actual output images, not
just log/structural checks. One graph, one queue press: analyzer emits
structured JSON, router deterministically picks GENERATE (Z-Image Turbo)
or EDIT (Qwen Image Edit 2511), only the selected branch's models load and
run, single `SaveImage` output.

## A real mistake, caught and fixed before declaring success

First submission attempt used the Z-Image Turbo branch's model paths as
named in ComfyUI's *official* template
(`image_z_image_turbo.json`: `z_image_turbo_bf16.safetensors`,
`qwen_3_4b.safetensors`) without verifying they were actually installed in
this ComfyUI - they were not. `POST /prompt` returned a `prompt_id`
successfully (no HTTP error), but the response body's `node_errors`/log
showed `[ERROR] Failed to validate prompt for output save: ... Value not
in list ... Output will be ignored`. The graph "completed" with
`status_str: success` and empty `outputs: {}` - a silent, easy-to-miss
failure if only the HTTP status is checked, not the response body or log.
Root cause: didn't verify installed model paths before using them
(`PROJECT_RULES.md`'s own mandatory rule), and only checked HTTP
success/failure, not the response body's `node_errors` field or the log.
Fixed `submit_and_check.py` to check both going forward.

Corrected by checking `/object_info`'s actual `UNETLoader`/`CLIPLoader`
option lists: this ComfyUI has no `z_image_turbo_bf16.safetensors` or
`qwen_3_4b.safetensors` at all - Z-Image Turbo is installed as three
community/fine-tuned checkpoints (`jibMixZIT_v10.safetensors`,
`eventHorizon_zitV10-Q5_K_M.gguf`, `zEpicrealism_turboV1Fp8-Q5_K_M.gguf`)
and three GGUF text encoders (all already abliterated:
`Lockout-Qwen3-4b-zimage-hereticV2-q8.gguf`,
`mradermacher - Huihui-Qwen3-4B-abliterated-v2.Q8_0.gguf`,
`mradermacher - Josiefied-Qwen3-4B-abliterated-v2.Q8_0.gguf`) - none of
which had been documented anywhere as "the" V1 default before this. User's
explicit choice: `jibMixZIT_v10.safetensors` (UNet, keeps the official
template's `UNETLoader`/safetensors loader type) + `Lockout-Qwen3-4b-
zimage-hereticV2-q8.gguf` (CLIP, via `CLIPLoaderGGUF` - GGUF is the only
installed option for this text encoder at all).

## Graph shape

`LoadImage(source) -> QwenVLStructuredGGUF(analyzer) -> LoadJsonFromText ->
GetTextFromJson(key="task") -> easy compare(== "edit") -> easy
ifElse(on_true=edit-branch IMAGE, on_false=generate-branch IMAGE) ->
SaveImage`. Both branches fully built (UNet/CLIP/VAE load through
KSampler/VAEDecode to plain IMAGE), no `OUTPUT_NODE=True` node inside
either branch (per `RESULTS_lazy_switch.md`'s finding - a branch-local
output node would force it to execute as an execution root regardless of
the switch). `prompt` also extracted via `GetTextFromJson` and routed into
each branch's own text-conditioning input. Edit branch's negative prompt
kept dependent on the analyzer's own output (via `StringSubstring`,
`start=0, end=0` - always `""`) rather than a bare literal, matching the
E2/E3 fix's shape as defense in depth, even though the lazy-switch
architecture should make that scheduling defect structurally impossible
here (the boolean gating the switch is itself derived from the analyzer's
output, so the edit branch cannot enter the pending execution set before
the analyzer finishes) - not independently re-measured with VRAM
timestamps, flagged as a follow-up.

## Case 1: generate

Instruction: "Create a photorealistic product photo of a matte black
ceramic mug on a walnut desk in morning window light." No image edit
implied.

- Wall time: 44.66s.
- Log load lines: `ZImageTEModel_`, `Lumina2`, `AutoencodingEngine` (all
  Z-Image Turbo / generate-branch components) - **no** `QwenImage`/
  `QwenImageTEModel_` (edit-branch) lines anywhere.
- Output: `ImageDirector_router_00001_.png`, visually inspected - a
  photorealistic matte black mug on a wood-grained desk in front of a
  bright window, closely matching the instruction.
- No log `[ERROR]` lines.

## Case 2: edit

Instruction: "Remove only the blue square from the attached image. Keep
the red circle, background, and composition unchanged." Same synthetic
shapes image used throughout this project's testing.

- Wall time: 66.83s.
- Log load lines: `WanVAE` (this ComfyUI install's VAE dtype-check
  message, appears for both branches, not branch-specific),
  `QwenImageTEModel_`, `QwenImage` (edit-branch components) - **no**
  `ZImageTEModel_`/`Lumina2` (generate-branch) lines anywhere.
- Output: `ImageDirector_router_00002_.png`, visually inspected - the blue
  square is gone, the red circle and background are unchanged, matching
  the instruction exactly.
- No log `[ERROR]` lines.

## What this settles

- The full V1 router mechanism works end-to-end in the real production
  ComfyUI: structured JSON from the analyzer correctly and deterministically
  drives which of two fully-independent, expensive branches executes, and
  the lazy-switch design (`tests/router/RESULTS_lazy_switch.md`) correctly
  skips the unselected branch's entire model-loading/sampling chain in
  both directions, confirmed here with the real branches, not just cheap
  stand-ins.
- Both branches individually produce contextually-correct, instruction-
  matching output when selected - not just "some image," a visually
  verified correct one in each case (n=1 per direction).
- The submission/validation-checking gap that caused a silent
  empty-output "success" earlier is now closed in tooling
  (`submit_and_check.py`), and the specific model-path mistake that caused
  it is documented so it isn't quietly repeated.

## Codex review (same thread as the rest of this project's joint decisions)

Independent review of this result: evidence supports "V1 router works
end-to-end" for the scoped case (one analyzer, deterministic task
extraction, lazy branch switch, both real branches, one final `SaveImage`,
visual outputs matching the requested task in both directions). n=1 per
direction is adequate to mark the *mechanism* working - explicitly not a
reliability characterization; no repeat-seed screen needed before updating
`PROJECT_RULES.md`, as long as it's documented as such (see above).
`StringSubstring` kept on the edit negative prompt: fine as cheap defense
in depth. Lack of VRAM re-measurement for this specific combined graph:
not a blocker for router correctness, but must stay documented as
unresolved before any claim of production VRAM headroom.

Gap flagged: `submit_and_check.py`'s `node_errors` check alone wasn't
enough - it still let a human misread a later empty/errored run as a pass
without also asserting `status.completed`, "no `[ERROR]` in log", and
"an image was actually produced". Fixed: `wait_and_report()` now raises on
any of those three conditions instead of just reporting them. Also flagged
as a minor, non-blocking gap: the same missing-`node_errors`-check pattern
exists in `tests/schema/analyzer-json*/submit_and_capture.py` and
`tests/vram/combined-multiref/submit_and_monitor.py` - those runs' saved
artifacts are not invalidated (evidence was cross-checked another way at
the time), but a future reuse of either script should get the same guard,
or the project should consolidate on one shared submit helper. Not fixed
in this pass - out of scope for the router milestone itself, noted here so
it isn't lost.

## What this does not settle

- n=1 per direction - no repeat-seed reliability screen for the router
  itself yet.
- Multi-reference (`image2`/`image3`) routing - this test is scoped to the
  single-source-image case only, matching Test C's validated shape;
  availability-specific schema selection as real router logic (building
  the right schema variant from however many images are actually supplied)
  remains a separate, open item per `PROJECT_RULES.md`.
- VRAM margins for the combined router graph have not been measured the
  way E2/E3 measured the old analyzer+editor path - the lazy-switch
  design's claimed side-benefit (naturally sequential analyzer-then-branch
  execution) is a design expectation, not yet independently VRAM/timestamp
  verified.
- Plan/content quality beyond "task routed correctly and branch output
  looked right" (e.g. `is_local_region` accuracy, edit locality on a real
  photo, identity preservation) remains out of scope, per this project's
  standing evidence rules.
- The Z-Image Turbo checkpoint/text-encoder choice made here
  (`jibMixZIT_v10` + `Lockout-Qwen3-4b-zimage-hereticV2`) was picked in
  this session for this test; not benchmarked against the other two
  UNet/three CLIP alternatives sitting on disk.
