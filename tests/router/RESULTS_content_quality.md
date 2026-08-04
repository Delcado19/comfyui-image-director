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

## What this does not settle / open concern

- n=1 per case - no repeat-seed screen, matches this project's existing
  scope limitation for all such tests.
- Root cause of case 3's failure not isolated (Qwen Image Edit's reference
  handling vs. prompt phrasing vs. a fundamental limitation of solid-color-
  swatch references for garment-level edits) - candidate follow-up: retry
  case 3 with a photographic reference image (e.g. a photo of a red
  garment) instead of a flat color swatch, to see whether the failure is
  specific to abstract color references.
- The `image2.role: "source"` schema gap is documented, not fixed.
- No systematic identity-preservation check (e.g. face similarity scoring)
  was done - "identity preserved" here is a visual judgment call, not a
  measured metric.
- Only one real photo tested - no variation across subjects, lighting, or
  photo composition.
