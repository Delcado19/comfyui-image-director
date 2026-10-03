"""
Analyzer-quality pre-screen (Codex-designed, thread
019fd14f-0515-7a91-958a-ce162f468ce2), no image generation / no KSampler.

Follow-up to RESULTS_analyzer_field_reliability.md's 5/5 failure
(is_local_region wrong, edits[] collapsed to "entire image"/"full image")
for case 3 under the router's CURRENT (original-baseline) GUIDANCE/schema.

Independent finding: tests/schema/analyzer-json-structured/
PROMPT_EXPERIMENT_2026-08-03.md already tried a fix for exactly this
problem class - schema property reorder (structured fields before
user_instruction/prompt) + explicit "use a named subject, not entire
image, when one exists" wording - and it fixed this exact shape of case
(single edit, 1 reference image, "edit_reference_2image") cleanly at the
time. It was reverted only because of a SEPARATE regression in the
3-image/multi-edit case, not because it failed for 1-reference cases.

This script re-tests that same v3 schema-order + wording combination
(Codex: test both together, not wording alone - the prior result was for
the combination), scoped ONLY to reference_count<=1 (does not touch or
claim anything about the 2-reference/multi-edit path, which stays a
known-separate unsolved problem), on the actual case-3 instruction/images
instead of the old synthetic shapes fixture. Per Codex, retesting is not
redundant: current analyzer weights are abliterated Q4_K_M (not the old
Q4_K_S pair runs_v3 used), the images are a real photo + color swatch (not
synthetic shapes), and the schema's reference-role enum has since been
narrowed (REFERENCE_ROLE_ENUM_ORDERED excludes "source" for image2, unlike
the old runs_v3 schema which still allowed it).

Scoring: same as analyzer_field_reliability.py.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director")
from image_director.edit_plan_schema import GENERATE_PLAN, REFERENCE_ROLE_ENUM_ORDERED, OP_ENUM

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf"

# v3 guidance (PROMPT_EXPERIMENT_2026-08-03.md's runs_v3), adapted from the
# hardcoded shapes-fixture wording to the router's general-instruction style
# (reference_count<=1 scope only - the 3-image path is untouched).
GUIDANCE_V3 = """You are creating a structured plan for an image generation/editing pipeline. schema_version is always "1.0". If this is a text-to-image request unrelated to the attached image(s), use task="generate" - ignore the attached image(s) entirely in that case. If the request modifies the attached image, use task="edit". Picture 1 (image1) is the source image being edited{reference_note}. Set is_local_region to true only if just one specific subject/region should change and everything else must stay the same (false if the whole image is being transformed/restyled). List "images" with image1 (role "source"){reference_role_note}. For edits[]:
- Only list things that actually change.
- If the instruction names a specific object, garment, or region, use that as subject/region.
- Use subject "entire image" and region "full image" only for global edits where no more specific changed subject exists.
- Put unchanged objects, regions, background, layout, and composition only in preserve[], not in edits[].
- The prompt field must be one clean instruction for an image model: no markdown, no schema terms, no role inventory, no analysis.

Instruction: {instruction}"""

# Reordered edit schema: structured fields (is_local_region/images/edits/
# preserve) before user_instruction/prompt, matching runs_v3's property
# order - grammar-constrained decoding emits required properties in
# properties-dict order (confirmed via llama_grammar.py's SchemaConverter,
# same fact PROMPT_EXPERIMENT_2026-08-03.md already established).
def edit_plan_schema_v3(reference_count: int) -> dict:
    reference_keys = ["image2", "image3"][:reference_count]
    images_properties = {"image1": {"type": "object", "additionalProperties": False, "required": ["role"], "properties": {"role": {"const": "source"}}}}
    for key in reference_keys:
        images_properties[key] = {"type": "object", "additionalProperties": False, "required": ["role"], "properties": {"role": {"enum": list(REFERENCE_ROLE_ENUM_ORDERED)}}}

    edit_item_properties = {
        "subject": {"type": "string", "minLength": 1},
        "region": {"type": "string", "minLength": 1},
        "operation": {"enum": sorted(OP_ENUM)},
    }
    edit_item_required = ["subject", "region", "operation"]
    if reference_keys:
        edit_item_properties["reference_slots"] = {
            "type": "array", "minItems": 1,
            "items": {"enum": reference_keys} if len(reference_keys) > 1 else {"const": reference_keys[0]},
        }
        edit_item_required.append("reference_slots")

    edit_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "task", "is_local_region", "images", "edits", "preserve", "user_instruction", "prompt"],
        "properties": {
            "schema_version": {"const": "1.0"},
            "task": {"const": "edit"},
            "is_local_region": {"type": "boolean"},
            "images": {"type": "object", "additionalProperties": False, "required": ["image1"] + reference_keys, "properties": images_properties},
            "edits": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": False, "required": edit_item_required, "properties": edit_item_properties}},
            "preserve": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            "user_instruction": {"type": "string", "minLength": 1},
            "prompt": {"type": "string", "minLength": 1},
        },
    }
    return {"oneOf": [GENERATE_PLAN, edit_schema]}


SCENE_WORDS = {"background", "scene", "environment", "entire image", "full image"}


def build(seed: int) -> dict:
    reference_note = " plus image2 (a reference image - give it a role and use reference_slots on any edits[] entry that draws on it)"
    reference_role_note = " and image2 (pick the best-fitting role). Cite image2 in reference_slots for the edit that uses it"
    prompt_text = GUIDANCE_V3.format(
        reference_note=reference_note,
        reference_role_note=reference_role_note,
        instruction="Change the color of the woman's leather dress to match the color shown in the reference image.",
    )
    schema = edit_plan_schema_v3(reference_count=1)
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "analyzer": {
            "class_type": "QwenVLStructuredGGUF",
            "inputs": {
                "model_path": MODEL_PATH, "mmproj_path": MMPROJ_PATH,
                "prompt": prompt_text, "json_schema": json.dumps(schema),
                "max_tokens": 512, "temperature": 0.1, "top_p": 0.9,
                "repetition_penalty": 1.2, "seed": seed, "ctx": 8192,
                "gpu_layers": -1, "keep_model_loaded": False,
                "free_vram_before_load": True,
                "image": ["src", 0], "image2": ["ref2", 0],
            },
        },
        "plan_preview": {"class_type": "PreviewAny", "inputs": {"source": ["analyzer", 0]}},
    }
    return {"prompt": graph}


def score(raw_text: str) -> dict:
    try:
        plan = json.loads(raw_text)
    except Exception as exc:
        return {"parse_error": str(exc)}

    edits = plan.get("edits", [])
    dress_edits = [e for e in edits if not any(w in (e.get("subject", "") + " " + e.get("region", "")).lower() for w in SCENE_WORDS)]

    return {
        "task": plan.get("task"),
        "is_local_region": plan.get("is_local_region"),
        "num_edits": len(edits),
        "edit_subjects_regions": [(e.get("subject"), e.get("region"), e.get("reference_slots")) for e in edits],
        "scene_word_in_edit_subject_or_region": len(dress_edits) < len(edits),
        "prompt_contains_background": "background" in plan.get("prompt", "").lower(),
        "preserve": plan.get("preserve"),
    }


if __name__ == "__main__":
    seeds = [int(s) for s in sys.argv[1:]] or [99002, 99003, 99004, 99005, 99006]
    results = []
    for seed in seeds:
        graph = build(seed)
        with open(f"tests/router/runs/AFRv3_{seed}.graph.json", "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)
        pid = submit(graph)
        result = poll_history(pid)
        outs = result["outputs"]
        raw_text = None
        for node_out in outs.values():
            texts = node_out.get("text")
            if texts:
                raw_text = texts[0]
                break
        row = {"seed": seed, "prompt_id": pid, "raw": raw_text, **score(raw_text or "")}
        results.append(row)
        print(json.dumps(row, indent=2))

    with open("tests/router/runs/AFRv3_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
