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
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from image_director.edit_plan_schema import edit_plan_schema  # noqa: E402

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\Qwen\Qwen2.5-VL-7B-Instruct-GGUF\Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\Qwen\Qwen2.5-VL-7B-Instruct-GGUF\Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf"


CASES = {
    "generate": {
        "instruction": "Create a photorealistic product photo of a matte black ceramic mug on a walnut desk in morning window light.",
        "images": [],
        # source_image=True here (not False) is deliberate, not an oversight:
        # it preserves the exact schema this case was originally validated
        # with (oneOf(generate, single-image edit), even though no image is
        # actually wired in) - see PROJECT_RULES.md's evidence rules on not
        # silently changing validated behavior during a refactor. A stricter
        # source_image=False generate-only schema is available and may be
        # worth adopting later, just not folded into this pass.
        "schema": edit_plan_schema(source_image=True, reference_count=0),
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
        "schema": edit_plan_schema(source_image=True, reference_count=0),
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
        "schema": edit_plan_schema(source_image=True, reference_count=0),
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
        "schema": edit_plan_schema(source_image=True, reference_count=1),
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
        "schema": edit_plan_schema(source_image=True, reference_count=2),
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
