"""
First-party structured-analyzer test graphs, using the external
comfyui-qwenvl-structured-gguf node (QwenVLStructuredGGUF) instead of the
prompt-only AILab_QwenVL_GGUF_Advanced used by the historical, superseded
tests/schema/analyzer-json/ (which scored 0/3 - see that directory's
results). Full evidence trail for the new node itself lives in that sibling
repo's own probe/RESULTS*.md; this directory exists because
PROJECT_RULES.md's evidence rules want first-party verification in this
project too, not just borrowed conclusions.

Schema variants are availability-specific per case, not one shared schema:
the `images`/`reference_slots` shape only allows what images are actually
wired into that specific call. This directly avoids the known
reference_slots hallucination failure mode (documented in the node repo's
RESULTS_edit_plan_schema.md / RESULTS_node_queue.md): the model referenced
a non-existent image2 when the schema allowed it even though only image1
was ever provided. Narrowing the schema per call makes that grammatically
impossible instead of merely instructing against it.
"""
import json
import sys

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\Qwen\Qwen2.5-VL-7B-Instruct-GGUF\Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\Qwen\Qwen2.5-VL-7B-Instruct-GGUF\Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf"

GENERATE_PLAN = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "task", "user_instruction", "prompt"],
    "properties": {
        "schema_version": {"const": "1.0"},
        "task": {"const": "generate"},
        "user_instruction": {"type": "string", "minLength": 1},
        "prompt": {"type": "string", "minLength": 1},
    },
}

IMAGE_SLOT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["role"],
    "properties": {
        "role": {
            "enum": [
                "source", "garment_reference", "material_style_reference",
                "identity_reference", "object_reference", "pose_reference",
                "scene_reference", "other_reference",
            ]
        }
    },
}

EDIT_OP_ENUM = {"replace", "add", "remove", "adjust", "restyle"}


def edit_plan_single_image():
    """images: image1 only. edits[] has no reference_slots property at all -
    grammatically impossible to hallucinate a reference to a nonexistent
    image2/image3."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "task", "user_instruction", "prompt",
            "is_local_region", "images", "edits", "preserve",
        ],
        "properties": {
            "schema_version": {"const": "1.0"},
            "task": {"const": "edit"},
            "user_instruction": {"type": "string", "minLength": 1},
            "prompt": {"type": "string", "minLength": 1},
            "is_local_region": {"type": "boolean"},
            "images": {
                "type": "object",
                "additionalProperties": False,
                "required": ["image1"],
                "properties": {
                    "image1": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["role"],
                        "properties": {"role": {"const": "source"}},
                    },
                },
            },
            "edits": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["subject", "region", "operation"],
                    "properties": {
                        "subject": {"type": "string", "minLength": 1},
                        "region": {"type": "string", "minLength": 1},
                        "operation": {"enum": sorted(EDIT_OP_ENUM)},
                    },
                },
            },
            "preserve": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        },
    }


def edit_plan_two_image():
    """images: image1 + image2, both required. edits[] requires
    reference_slots == ["image2"] - image2 genuinely exists for this call."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "task", "user_instruction", "prompt",
            "is_local_region", "images", "edits", "preserve",
        ],
        "properties": {
            "schema_version": {"const": "1.0"},
            "task": {"const": "edit"},
            "user_instruction": {"type": "string", "minLength": 1},
            "prompt": {"type": "string", "minLength": 1},
            "is_local_region": {"type": "boolean"},
            "images": {
                "type": "object",
                "additionalProperties": False,
                "required": ["image1", "image2"],
                "properties": {
                    "image1": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["role"],
                        "properties": {"role": {"const": "source"}},
                    },
                    "image2": IMAGE_SLOT,
                },
            },
            "edits": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["subject", "region", "operation", "reference_slots"],
                    "properties": {
                        "subject": {"type": "string", "minLength": 1},
                        "region": {"type": "string", "minLength": 1},
                        "operation": {"enum": sorted(EDIT_OP_ENUM)},
                        "reference_slots": {"type": "array", "minItems": 1, "items": {"const": "image2"}},
                    },
                },
            },
            "preserve": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        },
    }


def edit_plan_three_image():
    """images: image1 + image2 + image3, all required. edits[] requires
    reference_slots, each a non-empty subset of {"image2","image3"} - image1
    is the source, never a valid reference to itself."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "task", "user_instruction", "prompt",
            "is_local_region", "images", "edits", "preserve",
        ],
        "properties": {
            "schema_version": {"const": "1.0"},
            "task": {"const": "edit"},
            "user_instruction": {"type": "string", "minLength": 1},
            "prompt": {"type": "string", "minLength": 1},
            "is_local_region": {"type": "boolean"},
            "images": {
                "type": "object",
                "additionalProperties": False,
                "required": ["image1", "image2", "image3"],
                "properties": {
                    "image1": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["role"],
                        "properties": {"role": {"const": "source"}},
                    },
                    "image2": IMAGE_SLOT,
                    "image3": IMAGE_SLOT,
                },
            },
            "edits": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["subject", "region", "operation", "reference_slots"],
                    "properties": {
                        "subject": {"type": "string", "minLength": 1},
                        "region": {"type": "string", "minLength": 1},
                        "operation": {"enum": sorted(EDIT_OP_ENUM)},
                        "reference_slots": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"enum": ["image2", "image3"]},
                        },
                    },
                },
            },
            "preserve": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        },
    }


CASES = {
    "generate": {
        "instruction": "Create a photorealistic product photo of a matte black ceramic mug on a walnut desk in morning window light.",
        "images": [],
        "schema": {"oneOf": [GENERATE_PLAN, edit_plan_single_image()]},
        "guidance": (
            'You are creating a structured plan for an image generation/editing pipeline. '
            'schema_version is always "1.0". No image is attached - this is a text-to-image '
            'request, use task="generate".\n\nInstruction: {instruction}'
        ),
        "expect_task": "generate",
        "expect_is_local_region": None,
    },
    "edit_local": {
        "instruction": "In the attached image, remove only the blue square. Keep the red circle, the background, and the composition unchanged.",
        "images": ["imgdir_jsontest_shapes.png"],
        "schema": {"oneOf": [GENERATE_PLAN, edit_plan_single_image()]},
        "guidance": (
            'You are creating a structured plan for an image generation/editing pipeline. '
            'schema_version is always "1.0". task="edit". Only one image (image1, the source) '
            'is attached. Set is_local_region to true only if just one specific subject/region '
            'should change and everything else must stay the same (false if the whole image is '
            'being transformed/restyled). List "images" with only image1 (role "source"). '
            "Describe the needed edit(s) and list what must be preserved.\n\nInstruction: {instruction}"
        ),
        "expect_task": "edit",
        "expect_is_local_region": True,
    },
    "edit_global": {
        "instruction": "Restyle the attached image as a clean pencil sketch. Keep the same shapes, layout, and framing.",
        "images": ["imgdir_jsontest_shapes.png"],
        "schema": {"oneOf": [GENERATE_PLAN, edit_plan_single_image()]},
        "guidance": (
            'You are creating a structured plan for an image generation/editing pipeline. '
            'schema_version is always "1.0". task="edit". Only one image (image1, the source) '
            'is attached. Set is_local_region to true only if just one specific subject/region '
            'should change and everything else must stay the same (false if the whole image is '
            'being transformed/restyled). List "images" with only image1 (role "source"). '
            "Describe the needed edit(s) and list what must be preserved.\n\nInstruction: {instruction}"
        ),
        "expect_task": "edit",
        "expect_is_local_region": False,
    },
    "edit_reference_2image": {
        "instruction": "In image1, replace the blue square with a shape matching the reference shown in image2. Keep the red circle and background unchanged.",
        "images": ["imgdir_jsontest_shapes.png", "imgdir_multitest_1_star.png"],
        "schema": {"oneOf": [GENERATE_PLAN, edit_plan_two_image()]},
        "guidance": (
            'You are creating a structured plan for an image editing pipeline. schema_version '
            'is always "1.0". task="edit". Picture 1 (image1) is the source image being edited; '
            'Picture 2 (image2) is a reference shape to incorporate. Set is_local_region to true '
            '(only one region changes). List "images" with image1 (role "source") and image2 '
            "(pick the best-fitting role). Describe the edit, citing image2 in reference_slots. "
            "List what must be preserved.\n\nInstruction: {instruction}"
        ),
        "expect_task": "edit",
        "expect_is_local_region": True,
    },
    "edit_reference_3image": {
        "instruction": "In image1, replace the blue square with a shape matching the reference in image2, and replace the red circle with a shape matching the reference in image3. Keep the background unchanged.",
        "images": [
            "imgdir_jsontest_shapes.png",
            "imgdir_multitest_1_star.png",
            "imgdir_multitest_2_triangle.png",
        ],
        "schema": {"oneOf": [GENERATE_PLAN, edit_plan_three_image()]},
        "guidance": (
            'You are creating a structured plan for an image editing pipeline. schema_version '
            'is always "1.0". task="edit". Picture 1 (image1) is the source image being edited; '
            'Picture 2 (image2) and Picture 3 (image3) are two separate reference shapes to '
            'incorporate into two separate edits. Set is_local_region to true (only two specific '
            'regions change). List "images" with image1 (role "source"), image2, and image3 '
            "(pick the best-fitting role for each). Describe each edit as its own entry in "
            "\"edits\", citing exactly one of image2/image3 in that edit's reference_slots - do "
            "not combine both edits into one entry. List what must be preserved.\n\n"
            "Instruction: {instruction}"
        ),
        "expect_task": "edit",
        "expect_is_local_region": True,
    },
}


def build(case_name: str, seed: int) -> dict:
    case = CASES[case_name]
    prompt_text = case["guidance"].format(instruction=case["instruction"])

    graph = {}
    node_inputs = {
        "model_path": MODEL_PATH,
        "mmproj_path": MMPROJ_PATH,
        "prompt": prompt_text,
        "json_schema": json.dumps(case["schema"]),
        "max_tokens": 512,
        "temperature": 0.1,
        "top_p": 0.9,
        "repetition_penalty": 1.2,
        "seed": seed,
        "ctx": 8192,
        "gpu_layers": -1,
        "keep_model_loaded": False,
    }

    slot_names = ["image", "image2", "image3"]
    for i, filename in enumerate(case["images"]):
        node_id = str(10 + i)
        graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": filename}}
        node_inputs[slot_names[i]] = [node_id, 0]

    graph["1"] = {"class_type": "QwenVLStructuredGGUF", "inputs": node_inputs}
    graph["2"] = {"class_type": "PreviewAny", "inputs": {"source": ["1", 0]}}

    return {"prompt": graph}


if __name__ == "__main__":
    case_name = sys.argv[1]
    seed = int(sys.argv[2])
    print(json.dumps(build(case_name, seed), ensure_ascii=False))
