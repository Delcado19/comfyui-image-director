"""
Strict structural + task-classification checker for analyzer JSON output
against docs/schema/edit_plan.schema.json's V1 rules. Extends the
docs/schema design-phase scratchpad checker: now applied to raw analyzer
text (captured from PreviewAny via ComfyUI's /history), with case-specific
task/is_local_region expectations and a reference_slots ban (this test's
cases only ever have image1, never image2/3 - see build_graph.py).

A json.loads() failure is an unconditional fail - no repair or extraction
beyond whatever AILab_OutputCleaner already did inside the analyzer node
itself (out of this checker's control, see AGENTS.md's note on that node).
Does not grade semantic quality of edits/preserve content - that is
analyzer prompt/plan quality, a separate, still-unresolved project item
(PROJECT_RULES.md).
"""
import json
import sys

OP_ENUM = {"replace", "add", "remove", "adjust", "restyle"}
GENERATE_ALLOWED = {"schema_version", "task", "user_instruction", "prompt"}
EDIT_ALLOWED = GENERATE_ALLOWED | {"is_local_region", "images", "edits", "preserve"}


def check(raw_text: str, expect_task: str | None, expect_is_local_region: bool | None):
    errors = []
    try:
        plan = json.loads(raw_text)
    except Exception as exc:
        return [f"json.loads failed: {exc}"], None

    if not isinstance(plan, dict):
        return [f"top level is not a JSON object: {type(plan).__name__}"], plan

    if plan.get("schema_version") != "1.0":
        errors.append(f"schema_version != '1.0': {plan.get('schema_version')!r}")
    task = plan.get("task")
    if task not in ("generate", "edit"):
        errors.append(f"task not generate|edit: {task!r}")
    for req in ("schema_version", "task", "user_instruction", "prompt"):
        if req not in plan:
            errors.append(f"missing required field: {req}")
    for str_field in ("user_instruction", "prompt"):
        value = plan.get(str_field)
        if str_field in plan and not (isinstance(value, str) and value.strip()):
            errors.append(f"{str_field} must be a non-empty string, got: {type(value).__name__} {value!r}")

    if task == "generate":
        extra = set(plan.keys()) - GENERATE_ALLOWED
        if extra:
            errors.append(f"task=generate has forbidden/extra keys: {extra}")
    elif task == "edit":
        extra = set(plan.keys()) - EDIT_ALLOWED
        if extra:
            errors.append(f"task=edit has extra keys: {extra}")
        missing = {"is_local_region", "images", "edits", "preserve"} - set(plan.keys())
        if missing:
            errors.append(f"task=edit missing required: {missing}")
        images = plan.get("images", {})
        if not isinstance(images, dict) or list(images.keys()) != ["image1"]:
            errors.append(f"images must contain exactly image1 for this single-image test, got: {images!r}")
        elif images.get("image1", {}).get("role") != "source":
            errors.append(f"images.image1.role must be 'source', got: {images.get('image1', {}).get('role')!r}")
        edits = plan.get("edits", [])
        if not isinstance(edits, list) or len(edits) < 1:
            errors.append("edits must be a non-empty array")
        else:
            for e in edits:
                if not isinstance(e, dict):
                    errors.append(f"edit item is not an object: {e!r}")
                    continue
                for str_field in ("subject", "region"):
                    v = e.get(str_field)
                    if not (isinstance(v, str) and v.strip()):
                        errors.append(f"edit.{str_field} must be a non-empty string, got: {v!r}")
                if e.get("operation") not in OP_ENUM:
                    errors.append(f"edit.operation not in enum: {e.get('operation')!r}")
                if "reference_slots" in e:
                    errors.append(
                        f"edit item contains forbidden reference_slots for single-image test: {e.get('reference_slots')!r}"
                    )
        preserve = plan.get("preserve", [])
        if not isinstance(preserve, list) or len(preserve) < 1:
            errors.append("preserve must be a non-empty array")
        elif not all(isinstance(p, str) and p.strip() for p in preserve):
            errors.append(f"preserve items must all be non-empty strings, got: {preserve!r}")

    if expect_task is not None and task != expect_task:
        errors.append(f"expected task={expect_task!r}, got {task!r}")
    if expect_is_local_region is not None and plan.get("is_local_region") != expect_is_local_region:
        errors.append(f"expected is_local_region={expect_is_local_region!r}, got {plan.get('is_local_region')!r}")

    return errors, plan


if __name__ == "__main__":
    path = sys.argv[1]
    expect_task = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    expect_local = None
    if len(sys.argv) > 3 and sys.argv[3] != "-":
        expect_local = sys.argv[3] == "true"

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    errs, _ = check(raw, expect_task, expect_local)
    print(f"[{path}] {'OK' if not errs else 'FAIL'}")
    for e in errs:
        print(f"  - {e}")
    sys.exit(1 if errs else 0)
