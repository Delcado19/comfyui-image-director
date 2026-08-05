"""
Self-check for validate_edit_plan()'s check_consistency=True (diagnostic-
only, not wired into rendering - see RESULTS_analyzer_field_reliability_v3.md,
image_director/edit_plan_schema.py's PLACEHOLDER_SUBJECTS/PLACEHOLDER_REGIONS
comment). Uses a real captured sample from AFRv3_results.json (seed 99002)
to prove the new checks catch the exact failure that test measured, without
needing a live ComfyUI call.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director")
from image_director.edit_plan_schema import validate_edit_plan

# Real v3-guidance sample (AFRv3_results.json, seed 99002): specific subject
# ("woman's leather dress") but is_local_region=False and region="entire
# image" - the exact inconsistency the new checks target.
INCONSISTENT_RAW = json.dumps({
    "schema_version": "1.0", "task": "edit",
    "is_local_region": False,
    "images": {"image1": {"role": "source"}, "image2": {"role": "material_style_reference"}},
    "edits": [{"subject": "woman's leather dress", "region": "entire image", "operation": "replace", "reference_slots": ["image2"]}],
    "preserve": ["background"],
    "user_instruction": "Change the color of the woman's leather dress to match the color shown in the reference image.",
    "prompt": "change the color of the woman's leather dress to match the color from picture2",
})

# Fully consistent plan: specific subject, is_local_region=True, specific region.
CONSISTENT_RAW = json.dumps({
    "schema_version": "1.0", "task": "edit",
    "is_local_region": True,
    "images": {"image1": {"role": "source"}, "image2": {"role": "material_style_reference"}},
    "edits": [{"subject": "woman's leather dress", "region": "dress", "operation": "replace", "reference_slots": ["image2"]}],
    "preserve": ["background"],
    "user_instruction": "Change the dress color.",
    "prompt": "Change the dress color to blue.",
})

SLOTS = {"image1", "image2"}


def demo():
    # Default (check_consistency=False): existing structural-only behavior,
    # unaffected by the new checks - no regression for current callers.
    assert validate_edit_plan(INCONSISTENT_RAW, SLOTS) == []

    # Opt-in: both targeted inconsistencies detected.
    errors = validate_edit_plan(INCONSISTENT_RAW, SLOTS, check_consistency=True)
    assert any("is_local_region is False" in e for e in errors), errors
    assert any("edit.region is a" in e for e in errors), errors

    # Consistent plan: no false positives from the new checks.
    assert validate_edit_plan(CONSISTENT_RAW, SLOTS, check_consistency=True) == []

    print("OK: check_consistency catches the real AFRv3 seed-99002 inconsistency, no false positive on a clean plan.")


if __name__ == "__main__":
    demo()
