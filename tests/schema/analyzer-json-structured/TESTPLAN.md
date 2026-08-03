# First-party structured-analyzer test (QwenVLStructuredGGUF)

Supersedes `tests/schema/analyzer-json/` (historical, prompt-only,
`AILab_QwenVL_GGUF_Advanced`, scored 0/3 - kept unchanged for the record, not
deleted). This directory tests the same kind of structured JSON output, now
via the external node `comfyui-qwenvl-structured-gguf`
(`QwenVLStructuredGGUF`), which grammar-constrains decoding through
`llama-cpp-python`'s `response_format`. Full evidence trail for the node
itself lives in that sibling repo's `probe/RESULTS*.md`; this directory
exists for first-party verification in this project, per PROJECT_RULES.md's
evidence rules (verified-in-this-project over borrowed conclusions).

## Dependency

`comfyui-qwenvl-structured-gguf` (MIT, sibling dev repo at
`C:\Users\Delcado\Documents\Software_Projects\comfyui-qwenvl-structured-gguf`),
installed into `G:\ComfyUI-Easy-Install\ComfyUI\custom_nodes\` via a
directory junction (not a copy - the dev repo is the source of truth). Not
published to the Comfy Registry (user's explicit instruction: not until
feature-complete). Verify `GET /object_info/QwenVLStructuredGGUF` before
relying on it - it is not a well-known, permanently-installed dependency the
way core/registry nodes are.

## Availability-specific schemas, not one shared schema

Each case's `json_schema` only allows what images are actually wired into
that call (see `build_graph.py`'s `edit_plan_single_image()` vs.
`edit_plan_two_image()`). This is a deliberate fix for a real, reproduced
failure mode documented in the node repo: when a schema allowed
`reference_slots` even though only `image1` was ever provided, the model
twice hallucinated `reference_slots: ["image2"]` anyway. Narrowing the
schema per call makes that grammatically impossible instead of merely
instructing against it.

## Cases

| Case | Images | Schema variant | Expected `task` | Expected `is_local_region` |
|---|---|---|---|---|
| `generate` | none | oneOf(generate, single-image edit) | `generate` | n/a |
| `edit_local` | image1 (shapes.png) | oneOf(generate, single-image edit, no `reference_slots` property) | `edit` | `true` |
| `edit_global` | image1 (shapes.png) | same as `edit_local` | `edit` | `false` |
| `edit_reference_2image` | image1 (shapes.png) + image2 (star.png) | oneOf(generate, two-image edit, `reference_slots` required `["image2"]`) | `edit` | `true` |
| `edit_reference_3image` | image1 (shapes.png) + image2 (star.png) + image3 (triangle.png) | oneOf(generate, three-image edit, `reference_slots` required, subset of `{image2,image3}`) | `edit` | `true` |

## Checker (`check_json_plan.py`)

Strict `json.loads()`, no repair. Beyond structure/task/`is_local_region`:
checks that `images` keys exactly match what was actually provided for that
call, and - the router-side check PROJECT_RULES.md lists as still
unresolved and unenforceable by JSON Schema alone - that every
`reference_slots` value is actually a key present in `images` for that
specific response (not just a member of the schema's allowed enum).

## Guardrails

Same as every prior test in this project: `GET /queue` empty before
submitting, `POST /free` before the suite, `keep_model_loaded=false`
(the node's default), no editor/sampler stage, no global ComfyUI config
changes, no installs.

## Scope boundary

Structural/format-compliance and the reference_slots cross-field check only.
No image-quality, identity, edit-locality, or general plan-quality claim.
`analyzer prompt design and plan quality` remains a separate, unresolved
project item (PROJECT_RULES.md) - this test does not close it, even where a
response happens to be semantically correct.
