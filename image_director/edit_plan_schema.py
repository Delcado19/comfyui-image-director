"""
Reusable structured edit-plan schema generation and validation.

Extracted from tests/schema/analyzer-json-structured/build_graph.py's three
near-duplicate edit_plan_single_image()/edit_plan_two_image()/
edit_plan_three_image() functions and check_json_plan.py's check() function,
which the 5-case first-party test (see that directory's RESULTS.md)
validated end-to-end against the real QwenVLStructuredGGUF node. This module
exists so a future router doesn't have to reimplement proven schema/
validation logic that today only lives duplicated inside test scripts - see
PROJECT_RULES.md's "availability-specific schema selection/generation" and
"router-side semantic validation" unresolved items.

Two things this module deliberately does NOT do:
- It does not decide WHICH branch (generate vs edit) was correct - that's
  the analyzer's job, this only shapes/validates the JSON contract.
- It does not judge plan/content quality (is_local_region correctness,
  subject/region accuracy, etc.) - see
  tests/schema/analyzer-json-structured/PROMPT_EXPERIMENT_2026-08-03.md for
  why that isn't solved by schema/validation alone.

Restructured as oneOf (not the canonical docs/schema/edit_plan.schema.json's
if/then) because llama-cpp-python's JSON-Schema-to-grammar converter does
not support if/then conditionals - confirmed by reading llama_grammar.py's
SchemaConverter, not assumed. See docs/schema/edit_plan.grammar.schema.json.
"""
from __future__ import annotations

import json

OP_ENUM = {"replace", "add", "remove", "adjust", "restyle"}
# Ordered to match the original hand-written enum exactly (grammar output
# order is untested to matter for enums specifically, unlike properties
# order for objects, but kept identical for full reproducibility).
ROLE_ENUM_ORDERED = [
    "source", "garment_reference", "material_style_reference",
    "identity_reference", "object_reference", "pose_reference",
    "scene_reference", "other_reference",
]
ROLE_ENUM = set(ROLE_ENUM_ORDERED)
# image2/image3 are references, never the source - "source" is reserved for
# image1 (see _SOURCE_SLOT's const below). Without this narrower enum, a
# reference slot could legally claim role="source" and pass both grammar
# constraint and validate_edit_plan() despite being semantically wrong -
# found on a real photo, see comfyui-image-director's
# tests/router/RESULTS_content_quality.md case 3 (images.image2.role:
# "source").
REFERENCE_ROLE_ENUM_ORDERED = [r for r in ROLE_ENUM_ORDERED if r != "source"]
REFERENCE_ROLE_ENUM = set(REFERENCE_ROLE_ENUM_ORDERED)
# Ordered (not just the set - "required" list order matches the emission
# order the first-party test validated, even though JSON Schema itself
# treats "required" as an unordered set) plus the set form for fast
# membership checks elsewhere in this module.
GENERATE_KEYS_ORDERED = ["schema_version", "task", "user_instruction", "prompt"]
EDIT_KEYS_ORDERED = GENERATE_KEYS_ORDERED + ["is_local_region", "images", "edits", "preserve"]
GENERATE_KEYS = set(GENERATE_KEYS_ORDERED)
EDIT_KEYS = set(EDIT_KEYS_ORDERED)

GENERATE_PLAN = {
    "type": "object",
    "additionalProperties": False,
    "required": list(GENERATE_KEYS_ORDERED),
    "properties": {
        "schema_version": {"const": "1.0"},
        "task": {"const": "generate"},
        "user_instruction": {"type": "string", "minLength": 1},
        "prompt": {"type": "string", "minLength": 1},
    },
}

_IMAGE_SLOT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["role"],
    "properties": {"role": {"enum": list(REFERENCE_ROLE_ENUM_ORDERED)}},
}

_SOURCE_SLOT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["role"],
    "properties": {"role": {"const": "source"}},
}


def _edit_plan(reference_count: int) -> dict:
    """reference_count reference images (image2, and image3 if 2) plus the
    mandatory source image1. reference_count=0 means no reference_slots
    property exists at all on edits[] items - grammatically impossible to
    hallucinate a reference to a nonexistent image, the fix for the
    reference_slots hallucination documented in the sibling node repo's
    RESULTS_edit_plan_schema.md / RESULTS_node_queue.md."""
    reference_keys = ["image2", "image3"][:reference_count]

    images_properties = {"image1": _SOURCE_SLOT}
    for key in reference_keys:
        images_properties[key] = _IMAGE_SLOT

    edit_item_properties = {
        "subject": {"type": "string", "minLength": 1},
        "region": {"type": "string", "minLength": 1},
        "operation": {"enum": sorted(OP_ENUM)},
    }
    edit_item_required = ["subject", "region", "operation"]
    if reference_keys:
        edit_item_properties["reference_slots"] = {
            "type": "array",
            "minItems": 1,
            "items": {"enum": reference_keys} if len(reference_keys) > 1 else {"const": reference_keys[0]},
        }
        edit_item_required.append("reference_slots")

    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(EDIT_KEYS_ORDERED),
        "properties": {
            "schema_version": {"const": "1.0"},
            "task": {"const": "edit"},
            "user_instruction": {"type": "string", "minLength": 1},
            "prompt": {"type": "string", "minLength": 1},
            "is_local_region": {"type": "boolean"},
            "images": {
                "type": "object",
                "additionalProperties": False,
                "required": ["image1"] + reference_keys,
                "properties": images_properties,
            },
            "edits": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": edit_item_required,
                    "properties": edit_item_properties,
                },
            },
            "preserve": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        },
    }


def edit_plan_schema(source_image: bool, reference_count: int = 0, *, include_generate: bool = True) -> dict:
    """Build the response_format-ready schema for a call with the given
    image availability.

    source_image: whether an image1 (the thing being edited) is wired into
        this call at all. False means task can only be "generate" - there
        is nothing to edit.
    reference_count: how many additional reference images (image2, then
        image3) are wired in, beyond image1. Only meaningful when
        source_image is True. Must be 0, 1, or 2.
    include_generate: set False if the caller already knows task="edit"
        (e.g. a router re-requesting after a rejected generate response)
        and wants a schema that only allows the edit shape. Defaults to
        True - preserves the always-oneOf(generate, edit) shape the
        first-party test validated.
    """
    if reference_count not in (0, 1, 2):
        raise ValueError(f"reference_count must be 0, 1, or 2, got: {reference_count!r}")
    if not source_image and reference_count:
        raise ValueError("reference_count must be 0 when source_image is False - no image1 to attach references to")

    if not source_image:
        return GENERATE_PLAN

    edit_schema = _edit_plan(reference_count)
    if not include_generate:
        return edit_schema
    return {"oneOf": [GENERATE_PLAN, edit_schema]}


def validate_edit_plan(raw_text: str, provided_image_slots) -> list:
    """Strict json.loads(), no repair. Enforces the same
    additionalProperties:false shape as edit_plan_schema()'s output, plus
    the router-side semantic check JSON Schema cannot express on its own:
    every edits[].reference_slots value must be a key actually present in
    "images" for THIS response (never image1, which is the source, not a
    valid reference to itself) - see this module's docstring and
    docs/schema/edit_plan.grammar.schema.json's own $comment for why the
    schema alone can't guarantee that.

    Returns a list of human-readable error strings; empty list means valid.
    Does not judge task/is_local_region/reference-union correctness against
    an expected value - that's case-specific, left to the caller (see
    tests/schema/analyzer-json-structured/check_json_plan.py for an example
    of layering those expectations on top of this).
    """
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

        # Caller-side check: every edit_plan_schema() variant requires
        # image1. If provided_image_slots itself omits "image1" (a caller
        # bug, not a model bug), the keys-equality check below can't catch
        # a response that "correctly" mirrors that buggy input - so check
        # the contract explicitly, not just consistency with the caller.
        if "image1" not in provided_keys:
            errors.append(
                f"provided_image_slots {provided_keys} omits 'image1' - task=edit always requires a "
                "source image; this looks like a caller bug, not something a response could satisfy"
            )

        images = plan.get("images", {})
        if not isinstance(images, dict):
            errors.append(f"images is not an object: {images!r}")
        else:
            if set(images.keys()) != provided_keys:
                errors.append(f"images keys {set(images.keys())} != actually-provided slots {provided_keys}")
            if "image1" not in images:
                errors.append(f"images.image1 missing: {images!r}")
            for slot_name, slot_val in images.items():
                if not isinstance(slot_val, dict) or set(slot_val.keys()) != {"role"}:
                    errors.append(f"images.{slot_name} must be exactly {{'role': ...}}, got: {slot_val!r}")
                elif slot_name == "image1":
                    if slot_val.get("role") != "source":
                        errors.append(f"images.image1.role not in enum: {slot_val.get('role')!r}")
                elif slot_val.get("role") not in REFERENCE_ROLE_ENUM:
                    errors.append(
                        f"images.{slot_name}.role not in reference-role enum (image1 is the only slot allowed "
                        f"'source'): {slot_val.get('role')!r}"
                    )

        valid_reference_keys = provided_keys - {"image1"}
        edits = plan.get("edits", [])
        if not isinstance(edits, list) or len(edits) < 1:
            errors.append("edits must be non-empty array")
        else:
            allowed_edit_keys = {"subject", "region", "operation"} | (
                {"reference_slots"} if valid_reference_keys else set()
            )
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
                if valid_reference_keys:
                    if not (isinstance(ref_slots, list) and len(ref_slots) >= 1 and all(isinstance(s, str) for s in ref_slots)):
                        errors.append(f"reference_slots required (non-empty list of strings) when a reference image is available, got: {ref_slots!r}")
                elif ref_slots is not None and not (isinstance(ref_slots, list) and all(isinstance(s, str) for s in ref_slots)):
                    errors.append(f"reference_slots must be a list of strings: {ref_slots!r}")

                if isinstance(ref_slots, list):
                    for slot in ref_slots:
                        if slot not in valid_reference_keys:
                            errors.append(
                                f"edit references {slot!r} in reference_slots, but valid references for this "
                                f"call are {valid_reference_keys} (reference_slots-vs-images cross-field "
                                "violation, the known unenforceable-by-schema gap - includes image1 "
                                "referencing itself, which is never valid)"
                            )
        preserve = plan.get("preserve", [])
        if not isinstance(preserve, list) or len(preserve) < 1 or not all(isinstance(p, str) and p.strip() for p in preserve):
            errors.append(f"preserve invalid: {preserve!r}")

    return errors
