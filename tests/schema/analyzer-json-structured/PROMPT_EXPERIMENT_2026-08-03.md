# Prompt-quality experiment (2026-08-03) - not adopted, documented for the record

Joint Claude-Codex experiment following up on `RESULTS.md`'s baseline 5/5
structural pass, which also documented real content-quality problems even
though every response was structurally valid. Goal: see whether wording and
schema-property-order changes could fix those specific problems without
sacrificing structural reliability. **Result: partial improvement, one new
regression, high sampling variance - not adopted as the new gate.**
`build_graph.py` was reverted to the exact baseline version (`git checkout`)
after this experiment; the outputs below are preserved as evidence
(`runs_v2/`, `runs_v3/`) but were produced by a temporarily-modified,
now-reverted script, not the current one.

## What was changed (v2, then v3)

1. **Schema property order** (edit branch only): moved
   `is_local_region`/`images`/`edits`/`preserve` before
   `user_instruction`/`prompt` (baseline had `prompt` as field #4, before
   the structured fields). Verified via source read (`llama_grammar.py`'s
   `SchemaConverter`, confirmed by Codex): required object properties are
   emitted in `properties` dict order when no `prop_order` is supplied
   (this project's node doesn't supply one) - so this reordering does
   change generation order, it isn't cosmetic.
2. **v2 guidance additions** (three separate sentences): don't list
   unchanged things in `edits[]` (use `preserve[]` instead); use
   `subject="entire image"`/`region="full image"` for whole-image edits,
   never a `"*"` placeholder; keep `prompt` to one clean sentence, no
   markdown/meta-commentary.
3. **v3 guidance** (Codex's consolidated rewrite after v2 showed a new
   over-generalization problem): same intent, one unified block, more
   explicit that a named subject from the instruction should be used
   instead of "entire image" whenever one exists.

## Paired reruns, same seeds as the committed baseline

### v2 (schema reorder + 3-sentence guidance)

Fixed exactly the targeted problems in 3 of 4 edit cases:

- `edit_local`: baseline had spurious extra `edits[]` entries for things
  that should stay unchanged; v2 had exactly one edit, `preserve[]` used
  correctly. `is_local_region` correct.
- `edit_global`: baseline used `"subject":"*","region":"*"`; v2 used
  `"entire image"`/`"full image"` correctly, one edit only.
- `edit_reference_2image`: single clean edit, correct `reference_slots`.

New regression in the 4th case:

- `edit_reference_3image`: correct edit count (2) and correct
  `reference_slots` split (`{"image2"}`/`{"image3"}`), BUT both edits used
  `subject="entire image"`/`region="full image"` even though these are two
  distinct local edits with instruction-named subjects ("the blue square",
  "the red circle") - the model over-applied the new whole-image rule to
  cases that don't need it. `edit_local` showed a milder version of the
  same drift (subject correct, region said "full image" instead of a
  specific location).

### v3 (same reorder, consolidated/clarified guidance)

- `edit_local`: fixed cleanly - `subject="blue square"` (specific, correct),
  single edit, correct `preserve[]`.
- `edit_reference_2image`: fixed cleanly - specific subject/region, correct
  reference.
- `edit_global`: partial - still correctly used "entire image"/"full
  image", but now produced TWO edits instead of one (`operation="restyle"`
  and a spurious second `operation="add"` - nothing is being added by a
  pure restyle instruction).
- `edit_reference_3image`: **worse than v2 on this specific case** -
  collapsed both replacements into ONE edit citing `reference_slots:
  ["image2","image3"]` together (not split), and `user_instruction`
  ("blue square"+"picture 2") and `prompt` ("red circle"+"Picture 3") became
  internally inconsistent with each other and with the single edit entry.
  `preserve: ["entire image"]` was also semantically wrong (parts of the
  image are changing, so nothing is "entirely" preserved).

## Conclusion (joint, not adopted)

- **Grammar-constrained decoding solving structural JSON reliability
  stands, unaffected.** Every v2/v3 response was still valid, schema-
  conformant JSON at the pure-schema level.
- **Simple prompt hygiene fixes are real and reproducible for single-edit
  cases**: the edits-vs-preserve confusion and the `"*"` placeholder
  problem both went away cleanly and consistently across both wording
  passes, for `edit_local`/`edit_global`/`edit_reference_2image`.
- **Multi-edit composition (the 3-image case) and cross-field consistency
  between `user_instruction`/`prompt`/`edits` are not reliably fixed by
  prompt wording alone** at n=1-2 samples per variant, temperature 0.1.
  The 3-image case's behavior changed direction between v2 and v3 with the
  same seed, which reads as real sampling variance interacting with
  wording, not a monotonic improvement - exactly the kind of thing that
  needs a proper reliability screen (n>=3 per case) to characterize, which
  is out of scope for what was meant to be a quick wording pass.
- Per Codex's explicit recommendation: did not run a reliability screen on
  v3 (it failed the pre-screen acceptance bar), did not attempt a further
  wording iteration in this same pass (multiple rule restatements already
  failed to fix the 3-image composition problem, which is stronger evidence
  against "wording isn't explicit enough" than for it).

## If picked up again later

Treat as a new, separately-scoped experiment, not more iteration on the
same prompt: candidates mentioned but not tried are `temperature=0`
(remove sampling variance as a confound), concrete few-shot examples in the
prompt (show a correctly-split multi-edit response), or moving the
multi-edit-consistency check to the router/checker layer (reject and
re-request rather than trying to make one-shot generation perfect). Do not
keep piling additional imperative rules into the same prompt block.
