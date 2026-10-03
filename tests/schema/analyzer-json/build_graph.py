"""
Build the three analyzer JSON-schema-compliance smoke-test graphs (generate,
edit-local, edit-global). Extension of Test A/C's analyzer node usage
(docs/source/IMAGE_DIRECTOR_AUDIT.md SS13), now testing whether the analyzer
can emit valid JSON matching docs/schema/edit_plan.schema.json - not VRAM
scheduling (that is tests/vram/combined-multiref/, a separate, already
completed concern).

Analyzer + PreviewAny only - no editor/sampler stage, since this test is
about the analyzer's text output, not image generation. keep_model_loaded is
explicitly false, same mandatory rule as every other analyzer test in this
project (PROJECT_RULES.md).

The two edit cases use a purpose-made synthetic image
(input/imgdir_jsontest_shapes.png: red circle left, blue square right on a
plain background) instead of the E2/E3 VRAM test's flat-color placeholder
images, because this test needs content the analyzer can actually describe.

Only image1 (the source) is wired to the analyzer - see AGENTS.md's note on
AILab_QwenVL_GGUF_Advanced only exposing a single `image` input (batched
tensors collapse to element 0; multiple stills would need the separate
`video` input, untested, out of scope here). The prompt explicitly forbids
`reference_slots` in this single-image test for the same reason.
"""
import json
import sys

MODEL_NAME = "Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"

PREAMBLE = """Output ONLY one valid JSON object as your entire response. No markdown code fences, no explanation, no text before or after the JSON. The JSON object must be the edit plan itself, not wrapped in an envelope such as "output", "content", "final", or "text".

Required top-level keys for every response:
- "schema_version": the exact string "1.0"
- "task": either "generate" or "edit"
- "user_instruction": the instruction below, copied or lightly cleaned, as a string
- "prompt": the instruction rewritten as a clear, direct prompt for an image-generation or image-editing model

If task is "generate": include ONLY those four keys. Do not add is_local_region, images, edits, or preserve.

If task is "edit": include exactly these eight top-level keys and no others: "schema_version", "task", "user_instruction", "prompt", "is_local_region", "images", "edits", "preserve".
- "is_local_region": true if only one specific subject or region should change and everything else must stay exactly the same; false if the whole image should be transformed/restyled
- "images": an object with exactly one key, "image1", whose value is {{"role": "source"}}
- "edits": a non-empty array; each item has "subject" (string), "region" (string), and "operation" (one of exactly: replace, add, remove, adjust, restyle). For this single-image test, do not include "reference_slots" in any edit item; no image2 or image3 is available.
- "preserve": a non-empty array of strings naming what must stay unchanged

Instruction: {instruction}"""

CASES = {
    "generate": {
        "instruction": "Create a photorealistic product photo of a matte black ceramic mug on a walnut desk in morning window light.",
        "image": False,
        "expect_task": "generate",
        "expect_is_local_region": None,
    },
    "edit_local": {
        "instruction": "In the attached image, remove only the blue square. Keep the red circle, the background, and the composition unchanged.",
        "image": True,
        "expect_task": "edit",
        "expect_is_local_region": True,
    },
    "edit_global": {
        "instruction": "Restyle the attached image as a clean pencil sketch. Keep the same shapes, layout, and framing.",
        "image": True,
        "expect_task": "edit",
        "expect_is_local_region": False,
    },
}


def build(case_name: str, seed: int) -> dict:
    case = CASES[case_name]
    custom_prompt = PREAMBLE.format(instruction=case["instruction"])

    graph = {}
    analyzer_inputs = {
        "model_name": MODEL_NAME,
        "device": "auto",
        "preset_prompt": "\U0001f5bc️ Detailed Description",
        "custom_prompt": custom_prompt,
        "max_tokens": 512,
        "temperature": 0.1,
        "top_p": 0.9,
        "repetition_penalty": 1.2,
        "frame_count": 16,
        "ctx": 8192,
        "n_batch": 512,
        "gpu_layers": -1,
        "image_max_tokens": 4096,
        "top_k": 0,
        "pool_size": 4194304,
        "keep_model_loaded": False,
        "seed": seed,
    }

    if case["image"]:
        graph["1"] = {
            "class_type": "LoadImage",
            "inputs": {"image": "imgdir_jsontest_shapes.png"},
        }
        analyzer_inputs["image"] = ["1", 0]

    graph["2"] = {
        "class_type": "AILab_QwenVL_GGUF_Advanced",
        "inputs": analyzer_inputs,
    }
    graph["3"] = {
        "class_type": "PreviewAny",
        "inputs": {"source": ["2", 0]},
    }

    return {"prompt": graph}


if __name__ == "__main__":
    case_name = sys.argv[1]
    seed = int(sys.argv[2])
    print(json.dumps(build(case_name, seed), ensure_ascii=False))
