# First-party structured-analyzer test result

**5/5 structural pass**, via the real ComfyUI queue, using the external
`QwenVLStructuredGGUF` node with availability-specific schemas (see
`build_graph.py`, `TESTPLAN.md`). Supersedes `tests/schema/analyzer-json/`
(historical, prompt-only, 0/3 - kept unchanged for the record).

| Case | Result | Wall time |
|---|---|---|
| `generate` | PASS | 7.5s |
| `edit_local` | PASS | 8.7s |
| `edit_global` | PASS | 8.0s |
| `edit_reference_2image` | PASS | 9.9s |
| `edit_reference_3image` (1 source + 2 references) | PASS | 10.6s |

## `edit_reference_3image` (added after the initial 4-case run)

3 images: `image1` = source (shapes.png), `image2` = star.png,
`image3` = triangle.png. Instruction asks for two separate replacements,
each citing a different reference image. Beyond the generic checker, two
case-specific assertions (per Codex's review) both passed: the union of all
`edits[].reference_slots` across the response equals exactly
`{"image2", "image3"}` (both references actually used, not just one), and
`len(edits) == 2` (one edit per replacement, not combined into one entry).

```json
{
  "schema_version": "1.0",
  "task": "edit",
  "user_instruction": "In image1, replace the blue square with a shape matching the reference in image2, and replace the red circle with a shape matching the reference in image3.",
  "prompt": "\n\n### images\n- **image1**: source\n- **image2**: \n- **image3**: \n",
  "is_local_region": true,
  "images": {"image1": {"role": "source"}, "image2": {"role": "object_reference"}, "image3": {"role": "object_reference"}},
  "edits": [
    {"subject": "blue square", "region": "left", "operation": "replace", "reference_slots": ["image2"]},
    {"subject": "red circle", "region": "right", "operation": "replace", "reference_slots": ["image3"]}
  ],
  "preserve": ["background"]
}
```

Structurally clean and the reference_slots split is exactly right (image2
for the blue-square edit, image3 for the red-circle edit - not conflated).
The union-of-reference_slots and edit-count checks Codex asked for are now
built into `check_json_plan.py` itself (`expect_reference_union`,
`expect_edit_count` optional args), not just ad-hoc inline Python - reusable
for future runs, not just this one evidence pass.
Content quality is worse than the 2-image case this time: `prompt` is a
broken, incomplete markdown fragment ("### images\n- **image1**: source\n-
**image2**: \n- **image3**: \n"), not a usable image-editing instruction -
passes `minLength: 1` but is not fit for purpose. `region: "left"`/`"right"`
are also swapped relative to the actual image (the blue square is on the
right of `imgdir_jsontest_shapes.png`, the red circle on the left -
confirmed by viewing the file). Both are exactly the kind of content issue
this test deliberately does not screen for structurally - see below.

No `reference_slots`-vs-`images` cross-field violations (the router-side
check `check_json_plan.py` adds beyond pure schema validation) - the
availability-specific schema design (no `reference_slots` property at all
for single-image cases) prevented the hallucination pattern seen in the
node repo's own earlier tests, as intended.

**Checker hardening note:** Codex's review caught that the first version of
`check_json_plan.py` only checked presence of required fields, not
absence of extra/forbidden ones (no `additionalProperties:false`-equivalent
check at the top level, on `images`, or on `edits[]` items) - a real
test-evidence gap, since it could have silently passed a response with
extra hallucinated fields. Hardened the checker to enforce exact key sets
at every level, then re-ran it against the same 4 already-saved raw
outputs (no new live calls needed). **Result unchanged: still 4/4 OK** -
confirms the outputs were genuinely schema-shaped, not that the original
checker's gap had been masking a failure.

Second Codex pass caught one more gap: `reference_slots` was checked for
membership in `images` but not for (a) being required/non-empty when a
non-source reference image is actually available, or (b) excluding
`image1` itself as a valid reference (the source can't be its own
reference). Tightened to `valid_reference_keys = provided_keys - {"image1"}`
and made `reference_slots` mandatory whenever `valid_reference_keys` is
non-empty. Self-tested against two fabricated bad cases
(`reference_slots:["image1"]`, and a missing `reference_slots` when image2
was available) - both correctly FAIL. Re-ran against the same 4 saved
outputs again: still 4/4 OK.

## Content-quality observations (out of scope for pass/fail, documented honestly)

Structural pass does not mean the plans are good. Raw outputs in `runs/*.txt`.
Notable issues, none of which affect this test's PASS verdict since none
violate the schema or the reference_slots check:

- `edit_local` and `edit_global` both added spurious extra `edits[]` entries
  for things that should stay unchanged (e.g. `{"subject": "red_circle",
  "region": "keep", "operation": "restyle"}` - "restyle" is a real operation
  in the enum, but nothing should be "restyled" here; the instruction said
  keep it unchanged, not edit it). Passes structurally (valid enum value,
  non-empty strings) but reads as the model padding the edits list rather
  than accurately modeling the instruction.
- `edit_global`'s `edits[]` used `"subject": "*", "region": "*"` twice -
  passes `minLength: 1` but is a placeholder, not real content.
- `edit_reference_2image`'s `prompt` field contains garbled meta-text
  ("...using an object that matches exactly to what is seen as role
  'source' and pick best-fitting role for picture-2...") - reads like
  instruction-writing leaking into what should be a clean image-editing
  prompt.
- `edit_reference_2image`'s `edits[0].region: "left"` is spatially wrong -
  the blue square is on the right side of `imgdir_jsontest_shapes.png` (red
  circle left, blue square right, confirmed by viewing the file). Passes
  structurally (non-empty string) but is factually incorrect.

All of this is exactly what `PROJECT_RULES.md`'s "analyzer prompt design and
plan quality" unresolved item already covers - this test does not close
that item, even where a response happens to look reasonable at a glance.

## What this settles

- The Image Director project now has a validated, first-party-tested path
  to structurally reliable JSON output: `QwenVLStructuredGGUF` +
  availability-specific schemas, 5/5 across generate, local edit, global
  edit, a 2-image/1-reference edit case, and a 3-image/2-reference edit case
  with two separate reference-citing edits.
- The known `reference_slots` hallucination failure mode is closed for cases
  where the schema is correctly narrowed to actual image availability, and
  the same narrowing correctly scales to two simultaneous reference images
  (each edit cites exactly the reference it needs, not the other one or the
  source).

## What this does not settle

- Plan/content quality (see observations above) - unresolved, tracked
  separately.
- n=1 per case - no repeat-seed reliability screen in this first-party test
  (the sibling node repo's probes already did some of that; not duplicated
  here per the agreed scope).
- A single edit item requiring BOTH `image2` and `image3` together in one
  `reference_slots` list - not tested (only the two-separate-edits shape
  was tested; per Codex, that's a different planning-shape question, out
  of scope for this pass).
- No image-quality, identity, or edit-locality claim - this is
  infrastructure/format-compliance evidence only.
