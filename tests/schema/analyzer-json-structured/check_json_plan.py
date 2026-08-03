"""
Checker for the structured-analyzer test outputs. Strict json.loads(), no
repair. Enforces the same additionalProperties:false shape as the actual
response_format schemas in build_graph.py (generate: exactly 4 keys; edit:
exactly 8 keys; images: exactly the provided slots, each slot object exactly
{"role": ...}; each edits[] item: exactly subject/region/operation, plus
reference_slots only when the schema variant allows it) - a prior version of
this checker only checked presence of required fields, not absence of
extra/forbidden ones, which Codex's review caught as a real evidence gap
before any of the 4 saved runs had been re-verified against it.

Also enforces the router-side semantic check PROJECT_RULES.md lists as
unresolved: every edits[].reference_slots value must actually be a key
present in "images" - JSON Schema alone cannot express this cross-field
constraint (see docs/schema/edit_plan.grammar.schema.json's own $comment).
"""
import json
import sys

OP_ENUM = {"replace", "add", "remove", "adjust", "restyle"}
ROLE_ENUM = {
    "source", "garment_reference", "material_style_reference",
    "identity_reference", "object_reference", "pose_reference",
    "scene_reference", "other_reference",
}
GENERATE_KEYS = {"schema_version", "task", "user_instruction", "prompt"}
EDIT_KEYS = GENERATE_KEYS | {"is_local_region", "images", "edits", "preserve"}


def check(
    raw_text: str,
    expect_task,
    expect_is_local_region,
    provided_image_slots,
    allow_reference_slots,
    expect_reference_union=None,
    expect_edit_count=None,
):
    errors = []
    try:
        plan = json.loads(raw_text)
    except Exception as exc:
        return [f"json.loads failed: {exc}"]
    if not isinstance(plan, dict):
        return [f"top level not an object: {type(plan).__name__}"]

    if plan.get("schema_version") != "1.0":
        errors.append(f"schema_version != '1.0': {plan.get('schema_version')!r}")
    task = plan.get("task")
    if task not in ("generate", "edit"):
        errors.append(f"task not generate|edit: {task!r}")
    for field in ("user_instruction", "prompt"):
        v = plan.get(field)
        if not (isinstance(v, str) and v.strip()):
            errors.append(f"{field} must be non-empty string, got: {v!r}")

    provided_keys = set(provided_image_slots)

    if task == "generate":
        extra = set(plan.keys()) - GENERATE_KEYS
        if extra:
            errors.append(f"task=generate has forbidden/extra top-level keys: {extra}")
    elif task == "edit":
        extra = set(plan.keys()) - EDIT_KEYS
        if extra:
            errors.append(f"task=edit has extra top-level keys: {extra}")
        missing = {"is_local_region", "images", "edits", "preserve"} - set(plan.keys())
        if missing:
            errors.append(f"task=edit missing required top-level keys: {missing}")

        images = plan.get("images", {})
        if not isinstance(images, dict):
            errors.append(f"images is not an object: {images!r}")
        else:
            if set(images.keys()) != provided_keys:
                errors.append(f"images keys {set(images.keys())} != actually-provided slots {provided_keys}")
            for slot_name, slot_val in images.items():
                if not isinstance(slot_val, dict) or set(slot_val.keys()) != {"role"}:
                    errors.append(f"images.{slot_name} must be exactly {{'role': ...}}, got: {slot_val!r}")
                elif slot_val.get("role") not in ROLE_ENUM:
                    errors.append(f"images.{slot_name}.role not in enum: {slot_val.get('role')!r}")
            if "image1" in images and images.get("image1", {}).get("role") != "source":
                errors.append(f"images.image1.role != source: {images.get('image1')!r}")

        edits = plan.get("edits", [])
        if not isinstance(edits, list) or len(edits) < 1:
            errors.append("edits must be non-empty array")
        else:
            if expect_edit_count is not None and len(edits) != expect_edit_count:
                errors.append(f"expected {expect_edit_count} edit(s), got {len(edits)}")

            allowed_edit_keys = {"subject", "region", "operation"} | (
                {"reference_slots"} if allow_reference_slots else set()
            )
            reference_union = set()
            for e in edits:
                if not isinstance(e, dict):
                    errors.append(f"edit item is not an object: {e!r}")
                    continue
                extra_edit_keys = set(e.keys()) - allowed_edit_keys
                if extra_edit_keys:
                    errors.append(f"edit item has forbidden/extra keys: {extra_edit_keys}")
                for f in ("subject", "region"):
                    if not (isinstance(e.get(f), str) and e.get(f).strip()):
                        errors.append(f"edit.{f} not a non-empty string: {e.get(f)!r}")
                if e.get("operation") not in OP_ENUM:
                    errors.append(f"edit.operation not in enum: {e.get('operation')!r}")

                ref_slots = e.get("reference_slots")
                # A non-source reference set: image1 is the thing being
                # edited, not a valid reference to itself.
                valid_reference_keys = provided_keys - {"image1"}
                if allow_reference_slots and valid_reference_keys:
                    if not (isinstance(ref_slots, list) and len(ref_slots) >= 1 and all(isinstance(s, str) for s in ref_slots)):
                        errors.append(f"reference_slots required (non-empty list of strings) when a reference image is available, got: {ref_slots!r}")
                elif ref_slots is not None and not (isinstance(ref_slots, list) and all(isinstance(s, str) for s in ref_slots)):
                    errors.append(f"reference_slots must be a list of strings: {ref_slots!r}")

                if isinstance(ref_slots, list):
                    reference_union.update(s for s in ref_slots if isinstance(s, str))
                    # Router-side check: values must actually exist as a
                    # non-source reference image for THIS response, not just
                    # be schema-legal or merely present under "images".
                    for slot in ref_slots:
                        if slot not in valid_reference_keys:
                            errors.append(
                                f"edit references {slot!r} in reference_slots, but valid references for this "
                                f"call are {valid_reference_keys} (reference_slots-vs-images cross-field "
                                "violation, the known unenforceable-by-schema gap - includes image1 "
                                "referencing itself, which is never valid)"
                            )

            if expect_reference_union is not None and reference_union != set(expect_reference_union):
                errors.append(
                    f"expected the union of all edits[].reference_slots to be {set(expect_reference_union)}, "
                    f"got {reference_union} (e.g. only one reference image actually cited, or an extra one)"
                )
        preserve = plan.get("preserve", [])
        if not isinstance(preserve, list) or len(preserve) < 1 or not all(isinstance(p, str) and p.strip() for p in preserve):
            errors.append(f"preserve invalid: {preserve!r}")

    if expect_task is not None and task != expect_task:
        errors.append(f"expected task={expect_task!r}, got {task!r}")
    if expect_is_local_region is not None and plan.get("is_local_region") != expect_is_local_region:
        errors.append(f"expected is_local_region={expect_is_local_region!r}, got {plan.get('is_local_region')!r}")

    return errors


if __name__ == "__main__":
    # Positional: path, expect_task, expect_is_local_region, provided_slots,
    # allow_reference_slots, [expect_reference_union], [expect_edit_count].
    # "-" means "no expectation for this field".
    path = sys.argv[1]
    expect_task = sys.argv[2] if sys.argv[2] != "-" else None
    expect_local = None if sys.argv[3] == "-" else (sys.argv[3] == "true")
    provided_slots = sys.argv[4].split(",") if sys.argv[4] != "-" else []
    allow_reference_slots = sys.argv[5] == "true" if len(sys.argv) > 5 else False
    expect_reference_union = (
        sys.argv[6].split(",") if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    )
    expect_edit_count = (
        int(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] != "-" else None
    )

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    errs = check(
        raw, expect_task, expect_local, provided_slots, allow_reference_slots,
        expect_reference_union, expect_edit_count,
    )
    print(f"[{path}] {'OK' if not errs else 'FAIL'}")
    for e in errs:
        print(f"  - {e}")
    sys.exit(1 if errs else 0)
