"""
Checker for the structured-analyzer test outputs. Layers case-specific
expectations (task, is_local_region, reference union, edit count) on top of
image_director.edit_plan_schema.validate_edit_plan(), which does the
general-purpose structural + reference_slots-cross-field validation - see
that module's docstring for what it covers and why (it used to be
duplicated here; extracted so a future router can reuse it without
reimplementing it).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from image_director.edit_plan_schema import validate_edit_plan  # noqa: E402


def check(
    raw_text: str,
    expect_task,
    expect_is_local_region,
    provided_image_slots,
    allow_reference_slots,
    expect_reference_union=None,
    expect_edit_count=None,
):
    errors = validate_edit_plan(raw_text, provided_image_slots)
    if errors and errors[0].startswith(("json.loads failed", "top level not an object")):
        return errors  # can't inspect further, nothing else to check

    try:
        plan = json.loads(raw_text)
    except Exception:
        return errors  # already recorded above

    task = plan.get("task") if isinstance(plan, dict) else None

    # allow_reference_slots is a redundant caller-side hint (the schema
    # variant already encodes whether reference images exist) - cross-check
    # it against what validate_edit_plan derived from provided_image_slots
    # instead of trusting it blindly, to catch caller/test mistakes.
    has_reference_images = bool(set(provided_image_slots) - {"image1"})
    if allow_reference_slots != has_reference_images:
        errors.append(
            f"allow_reference_slots={allow_reference_slots} does not match provided_image_slots "
            f"{provided_image_slots} (has_reference_images={has_reference_images}) - check the test's own arguments"
        )

    if task == "edit" and isinstance(plan, dict):
        if expect_edit_count is not None:
            edits = plan.get("edits", [])
            if not (isinstance(edits, list) and len(edits) == expect_edit_count):
                errors.append(f"expected {expect_edit_count} edit(s), got {len(edits) if isinstance(edits, list) else edits!r}")

        if expect_reference_union is not None:
            reference_union = set()
            for e in plan.get("edits", []) if isinstance(plan.get("edits"), list) else []:
                if isinstance(e, dict) and isinstance(e.get("reference_slots"), list):
                    reference_union.update(s for s in e["reference_slots"] if isinstance(s, str))
            if reference_union != set(expect_reference_union):
                errors.append(
                    f"expected the union of all edits[].reference_slots to be {set(expect_reference_union)}, "
                    f"got {reference_union} (e.g. only one reference image actually cited, or an extra one)"
                )

    if expect_task is not None and task != expect_task:
        errors.append(f"expected task={expect_task!r}, got {task!r}")
    if expect_is_local_region is not None and (not isinstance(plan, dict) or plan.get("is_local_region") != expect_is_local_region):
        errors.append(f"expected is_local_region={expect_is_local_region!r}, got {plan.get('is_local_region') if isinstance(plan, dict) else None!r}")

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
