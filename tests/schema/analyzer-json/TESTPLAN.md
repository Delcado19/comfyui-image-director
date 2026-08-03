# Analyzer JSON-schema-compliance smoke test

Joint Claude-Codex test plan (thread continuity: same discussion that
designed `docs/schema/edit_plan.schema.json`). Tests whether the installed
analyzer (Qwen2.5-VL 7B via `AILab_QwenVL_GGUF_Advanced`) can reliably emit
JSON matching that schema when explicitly instructed to, via prompt
engineering only. This is **not** the VRAM/scheduling test
(`tests/vram/combined-multiref/`, already completed) and does **not** run
the editor/sampler stage.

## Why this is scoped narrowly

Reading `AILab_QwenVL_GGUF.py` and `AILab_OutputCleaner.py` (both in
`G:\ComfyUI-Easy-Install\ComfyUI\custom_nodes\ComfyUI-QwenVL\`) surfaced two
facts that shape this test:

1. `AILab_QwenVL_GGUF_Advanced` exposes only one `image` input. A batched
   IMAGE tensor collapses to element 0 (`_tensor_to_base64_png`); multiple
   distinct stills would need the separate `video` input repurposed as an
   image batch - untested anywhere in this project, out of scope here. So
   this test only ever gives the analyzer a single image (`image1`); it
   does **not** test `images.image2`/`image3` from the schema at all. That
   remains a separate, later test.
2. No JSON-mode / grammar-constrained decoding is used
   (`create_chat_completion` is called without `response_format`) - JSON
   validity depends entirely on the prompt. The system-role message is
   hardcoded in the node and not exposed to the workflow; all schema
   instructions live in `custom_prompt` (the user turn).

## Cases

Three cases, single synthetic test image
(`G:\ComfyUI-Easy-Install\ComfyUI\input\imgdir_jsontest_shapes.png`: red
circle left, blue square right, plain background - generated via ComfyUI's
own embedded Python + already-installed PIL, no new dependency):

| Case | Image | Instruction | Expected `task` | Expected `is_local_region` |
|---|---|---|---|---|
| `generate` | none | "Create a photorealistic product photo of a matte black ceramic mug on a walnut desk in morning window light." | `generate` | n/a |
| `edit_local` | shapes.png | "In the attached image, remove only the blue square. Keep the red circle, the background, and the composition unchanged." | `edit` | `true` |
| `edit_global` | shapes.png | "Restyle the attached image as a clean pencil sketch. Keep the same shapes, layout, and framing." | `edit` | `false` |

Full prompt template (shared preamble + per-case instruction): see
`build_graph.py`'s `PREAMBLE`/`CASES`. Hardened per Codex review: explicit
anti-envelope instruction, exact 8-key allowlist for `task=edit`, explicit
`reference_slots` ban (this test only ever has `image1`).

## Analyzer settings

Same model as Test A/C/E2/E3 (`Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf`),
`keep_model_loaded=false` (mandatory project rule), `max_tokens=512`,
`temperature=0.1` (low but non-zero, so the reliability-screen seeds carry
real sampling variance instead of repeating one deterministic path),
`top_p=0.9`, `repetition_penalty=1.2` (unchanged from prior tests), unique
`seed` per call for ComfyUI node-cache busting (same technique as E2/E3).

## Guardrails

- `GET /queue` must be empty before each submission (`submit_and_capture.py`
  aborts otherwise).
- `POST /free {"unload_models": true, "free_memory": true}` before the
  suite starts, to avoid warm-cache noise from unrelated prior work.
- Analyzer + `PreviewAny` only - no editor, no sampler, no `SaveImage`.
- No global ComfyUI config changes, no installs.

## Procedure (gated)

1. **Smoke gate**: run all 3 cases once each (3 analyzer calls). All 3 must
   pass the checker or the run stops here and is reported as a failure -
   per Codex: "the router cannot consume 'usually JSON'."
2. **Reliability screen**: only if the gate passes, repeat all 3 cases with
   2 more cache-busting seeds each (6 more calls, 9 total). Acceptance is
   9/9 valid + case-correct.

## Checker (`check_json_plan.py`)

Strict `json.loads()` on the raw captured text - a parse failure is an
unconditional fail, no repair beyond whatever `AILab_OutputCleaner` already
did inside the node itself. Enforces: `schema_version=="1.0"`, `task` enum,
generate's 4-key allowlist, edit's 8-key allowlist, `images=={"image1":
{"role":"source"}}`, non-empty `edits`/`preserve`, `operation` enum, no
`reference_slots` present, and the case's expected `task`/`is_local_region`.

**Not checked**: semantic quality of `edits`/`preserve` content (e.g.
whether the plan actually mentions "blue square") - that is analyzer
prompt/plan quality, a separate unresolved item per `PROJECT_RULES.md`, not
claimed by this test.

## Scope boundary

Infrastructure/format-compliance only. No image-quality, identity,
edit-locality, or plan-quality claim. Does not test `images.image2/3`
(multi-reference) at all - single-image only, per the node limitation above.
