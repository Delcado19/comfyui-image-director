# Plan/content quality and visual acceptance on a real photo — result

Closes (partially) the long-standing "plan/content quality" and "visual
acceptance tests on real photos" open items (`PROJECT_RULES.md`) - all
prior structural/VRAM tests used synthetic shape images
(`imgdir_jsontest_shapes.png`, solid-color swatches). User supplied a real
photo (`IMG_7148.jpg` - person, outdoor scene) and asked for 3
representative test cases: local object edit, global restyle,
multi-reference edit. This test does NOT establish reliability (n=1 per
case) - it is a first honest look with real content, not a screen.

## Method

Ran all 3 through the live router (`tests/router/build_router_graph.py`),
with a `PreviewAny` node wired to the analyzer's output added for this
test only (not committed to the shared script) so the raw structured JSON
plan could be inspected alongside the final image. Graphs:
`tests/router/runs/CQ_local.graph.json`, `CQ_global.graph.json`,
`CQ_multiref.graph.json`. Fresh seeds per case, no VRAM measurement (out
of scope here - see `tests/vram/router/` for that line of testing).

## Case 1 — local object removal: PASS (visual), plan partially wrong

Instruction: "Remove the beer bottle standing on top of the trash can.
Keep the woman, her clothing, and everything else in the scene
unchanged."

Analyzer plan: `is_local_region: true` (correct). `prompt` field:
accurate and specific - correctly names the bottle, its location relative
to the trash bin and the woman, and what to preserve. `edits[]`:
`{"subject": "entire image", "region": "full image", "operation":
"remove"}` - **wrong**. "Beer bottle" is an obvious specific subject; this
is the same placeholder-overuse pattern `tests/schema/analyzer-json-structured/RESULTS.md`
already documented on synthetic images, now confirmed on a real photo too.

**Visual result: correct.** Bottle removed from the trash can; the woman,
her pose, clothing, and the rest of the scene are all preserved. The
structural `edits[]` bug did not propagate to the output - see "Why plan
bugs didn't break case 1" below.

## Case 2 — global restyle: PASS (visual + plan)

Instruction: "Restyle the entire photo as a vintage 1970s film photograph
with warm faded colors and visible film grain."

Analyzer plan: `is_local_region: false` (correct), `edits: [{"subject":
"entire image", "region": "full image", "operation": "restyle"}]` - this
time the "entire image"/"full image" pattern is the *correct* usage per
the schema's own design intent (no more specific subject exists for a
whole-image style transform). `prompt` field: clean, minimal, on-target.

**Visual result: correct.** Warm, faded, grainy vintage tone applied
across the whole image; person/pose/composition recognizably preserved.

## Case 3 — multi-reference color match: FAIL (visual), plan wrong

Instruction: "Change the color of the woman's leather dress to match the
color shown in the reference image" + `image2` = a solid blue color
swatch (`imgdir_test_ref2.png`).

Analyzer plan, multiple issues:
- `is_local_region: false` - likely wrong; this reads as a single-garment
  color change, not a whole-image transform.
- `images.image2.role: "source"` - wrong. `image1` is the actual source;
  `image2` is a reference and should have a reference-type role (e.g.
  `material_style_reference`). This is not just a model mistake - per
  Codex's review, `edit_plan_schema.py`'s `_IMAGE_SLOT` role enum for
  reference images includes `"source"` as a legal value (`ROLE_ENUM_ORDERED`
  is shared unmodified between the source slot and reference slots), so
  this passes both grammar constraint and `validate_edit_plan()` despite
  being semantically wrong. **Real schema/validator design gap, not fixed
  in this pass** - candidate minimal fix: a reference-role enum that
  excludes `"source"`, plus a validator check
  (`slot_name != "image1" and role == "source"` -> reject).
- `edits[0]`: again `"subject": "entire image", "region": "full image"`
  instead of naming "the dress"/"leather dress" - same placeholder-overuse
  pattern as case 1.

The consumed `prompt` field itself, however, was reasonably specific: "The
woman is wearing a black leather dress that needs to be changed to match
the color from Reference Image #2, which appears as a solid blue
background. The rest should remain unchanged."

**Visual result: failed.** The entire image was tinted blue - sky,
buildings, background, pavement, everything - not just the dress, which
barely changed. This directly contradicts both the instruction and the
plan's own `preserve: ["background", "environment", ...]` list.

## Update: `image2.role="source"` schema gap fixed, case 3 re-tested

`image_director/edit_plan_schema.py`: `_IMAGE_SLOT`'s role enum now uses a
new `REFERENCE_ROLE_ENUM_ORDERED` (the full role list minus `"source"`),
and `validate_edit_plan()` checks `image1`'s role against `== "source"`
specifically and every other slot's role against that narrower enum
specifically. Self-tested (schema excludes `"source"` from `image2`'s
enum; validator rejects a fabricated `image2.role="source"` plan; accepts
a correct plan; all 5 previously-saved `analyzer-json-structured` outputs
still validate clean, no regression).

Re-ran case 3 (fresh seeds, same instruction/reference image). Result:
`images.image2.role` is now `"object_reference"` - the fix works for its
target, this role can no longer be `"source"`. **The visual output this
time was also correct** (dress turned blue, background/everything else
unchanged) - but this should not be attributed to the role-schema change,
since the render path does not consume `images[].role` (see below). The
consumed `prompt` also changed between samples: the failed run described
the reference swatch as "a solid blue background," while the passing run
described it as "a solid blue." That wording variance is the most
plausible observed contributor to the different visual outcome; this was
later isolated in a dedicated standalone A/B test and confirmed (see the
"Update: 'background'-word hypothesis isolated" section below) - graphs:
`tests/router/runs/CQ_multiref_fixed.graph.json`.

## Why plan bugs didn't break case 1, but case 3 still failed

Verified directly against `build_router_graph.py` (Codex cross-checked
this before I wrote it up): the router only extracts and consumes `task`
and `prompt` from the analyzer's structured JSON, via `GetTextFromJson` ->
`task_str`/`edit_prompt_str`. **`is_local_region`, `edits[]`, `preserve[]`,
`images[].role`, and `reference_slots` are generated by the analyzer but
never read by anything downstream in the current router graph** - they
don't drive `TextEncodeQwenImageEditPlus` or any other node. This is why
case 1's bad `edits[]` entry didn't matter (the actually-consumed `prompt`
was accurate) - and why case 3's structural bugs cannot be asserted as the
*cause* of its visual failure, only as correlated. The likely cause of
case 3's failure is either how Qwen Image Edit 2511 interprets a plain
solid-color reference image (plausibly reading it as a global color-grade
cue rather than "recolor this one garment"), or a real limitation of
prompt-only (no mask/region) garment-level color transfer with this model
- not investigated further here.

## What this settles

- Plan/content quality issues already documented on synthetic images
  (placeholder `"entire image"`/`"full image"` overuse) reproduce on a
  real photo, confirming they aren't an artifact of the synthetic test
  image's simplicity.
- A new, real schema design gap: reference image slots can legally claim
  `role: "source"`, passing both grammar and `validate_edit_plan()`.
- In the current router architecture, `edits[]`/`preserve[]`/`images[].role`
  are cosmetic - they do not affect the rendered output at all. Any future
  work that wants them to matter (e.g. per-edit application, a "did the
  render actually respect preserve[]" checker) needs new wiring, not just
  better analyzer prompting.
- Local edits and global restyles both worked correctly end-to-end
  (structurally and visually) on a real photo at n=1 each.
- Reference-based *local* attribute transfer (recolor one garment using a
  reference image) failed at n=1 - the model applied the reference
  globally instead of to the intended local subject.

## Update: "background"-word hypothesis isolated via standalone A/B test

The wording-variance hypothesis above ("not isolated in an A/B test") was
isolated in a follow-up standalone test that bypasses the analyzer (removes
analyzer sampling, schema, and `role` as confounds) and varies only the
consumed prompt's "background" clause, same seed/images otherwise. Result:
**confirmed** - "a solid blue background" produced the same whole-image
tint failure, "a solid blue" (no "background") produced the correct
dress-only result. See `tests/router/RESULTS_ab_background_word.md` for
full method and result. Root cause of case 3's original failure is now
explained (prompt wording, not the schema `role` gap) - not yet fixed at
the analyzer-prompting level (see that file's "does not settle" section).

## What this does not settle / open concern

- n=1 per case - no repeat-seed screen, matches this project's existing
  scope limitation for all such tests.
- Root cause of case 3's failure: **now explained** by the "background"-word
  A/B test above, not fully "isolated" in the sense of a fundamental model
  limitation being ruled out (single seed/image pair only) - candidate
  follow-up: retry case 3 with a photographic reference image (e.g. a photo
  of a red garment) instead of a flat color swatch, to see whether the
  failure is specific to abstract color references vs. specific to the
  "background" wording.
- The `image2.role: "source"` schema gap is fixed (see the "Update" section
  above) - `is_local_region` misclassification and the `"entire
  image"`/`"full image"` placeholder-overuse pattern are NOT fixed, still
  open.
- No systematic identity-preservation check (e.g. face similarity scoring)
  was done - "identity preserved" here is a visual judgment call, not a
  measured metric.
- Only one real photo tested - no variation across subjects, lighting, or
  photo composition.
