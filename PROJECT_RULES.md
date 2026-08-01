# ComfyUI Image Director — Project Rules

## Source priority

Read the project sources in this order:

1. `docs/source/IMAGE_DIRECTOR_AUDIT.md`
2. `docs/source/COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`

When the documents conflict, the newer technical audit has priority.

Do not silently combine contradictory claims. Record the conflict and use the
newer verified finding.

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
- FLUX.2: outside the Version-1 critical path until separately measured

The standalone analyzer implementation is unresolved.

Do not assume that the installed Qwen2.5-VL files used by Qwen Image Edit can
also be loaded directly as an independent analyzer.

The current audit states that analyzer-only Test A and combined Test C were
blocked pending a valid Layer-A analyzer decision.

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
2. State the exact scope of the proposed change.
3. Identify files that would be modified.
4. Explain the expected result and the test.
5. Change only one logically related part.
6. Run all locally possible validation.
7. Request the user's real ComfyUI runtime test when local validation is not
   sufficient.
8. Review the resulting diff.
9. Record unresolved risks honestly.

Do not bundle unrelated fixes.

## Evidence rules

Distinguish clearly between:

- verified installation facts
- findings from source-code inspection
- live runtime test results
- historical results from older hardware
- assumptions requiring a new test

File or node presence is not proof of runtime compatibility.

Disk size is not proof of simultaneous VRAM usage.

Do not claim visual quality, identity preservation or edit locality without an
actual controlled image test.

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

## Communication

Normal discussion may be in German.

Technical project documentation and persistent project files should be written
in English unless the user explicitly requests otherwise.

Prefer complete copy-and-paste-ready files and commands.

Report failures and uncertainty directly. Do not hide incomplete validation.
