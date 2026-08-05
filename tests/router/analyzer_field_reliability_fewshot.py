"""
Few-shot + v3-guidance pre-screen (Codex-designed, thread
019fd14f-0515-7a91-958a-ce162f468ce2), no image generation / no KSampler.

Follow-up to RESULTS_analyzer_field_reliability_v3.md's partial fix
(subject became specific, but is_local_region/region stayed wrong 5/5) and
a temp=0 n=1 sanity check (same day) confirming the failure is a stable
model mode, not sampling noise - the temp=0 sample reproduced the exact
same is_local_region=false / "entire image"/"full image" output as
temp=0.1's 5/5.

Tests PROMPT_EXPERIMENT_2026-08-03.md's other untried candidate: a
concrete few-shot example embedded in the guidance prompt (analogous but
not identical to case 3 - different garment/color/person, per Codex's
design, to avoid the model just copying text verbatim), combined with v3's
schema-order fix (not isolated - v3 already improved subject-naming, no
reason to throw that away for attribution purposes per Codex).

Scoring: same as analyzer_field_reliability.py/_v3.py.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director\tests\router")
sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director\tests\lib")
from analyzer_field_reliability_v3 import edit_plan_schema_v3, SCENE_WORDS, score
from comfy_submit import submit, poll_history

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf"

# Codex's example: analogous but not identical to case 3 (different
# garment, color, and subject gender) - demonstrates the desired
# is_local_region/region mapping without giving the model case 3's own
# answer to copy verbatim.
FEWSHOT_EXAMPLE = """
Example instruction:
In image1, change only the man's jacket to match the red fabric shown in image2. Keep his face, hair, pants, hands, pose, and the background unchanged.

Example JSON:
{
  "schema_version": "1.0",
  "task": "edit",
  "is_local_region": true,
  "images": {
    "image1": {"role": "source"},
    "image2": {"role": "material_style_reference"}
  },
  "edits": [
    {
      "subject": "man's jacket",
      "region": "jacket",
      "operation": "replace",
      "reference_slots": ["image2"]
    }
  ],
  "preserve": ["face", "hair", "pants", "hands", "pose", "background"],
  "user_instruction": "In image1, change only the man's jacket to match the red fabric shown in image2. Keep his face, hair, pants, hands, pose, and the background unchanged.",
  "prompt": "Change only the man's jacket to match the red fabric shown in image2. Keep his face, hair, pants, hands, pose, and background unchanged."
}
"""

GUIDANCE_FEWSHOT = """You are creating a structured plan for an image generation/editing pipeline. schema_version is always "1.0". If this is a text-to-image request unrelated to the attached image(s), use task="generate" - ignore the attached image(s) entirely in that case. If the request modifies the attached image, use task="edit". Picture 1 (image1) is the source image being edited{reference_note}. Set is_local_region to true only if just one specific subject/region should change and everything else must stay the same (false if the whole image is being transformed/restyled). List "images" with image1 (role "source"){reference_role_note}. For edits[]:
- Only list things that actually change.
- If the instruction names a specific object, garment, or region, use that as subject/region.
- Use subject "entire image" and region "full image" only for global edits where no more specific changed subject exists.
- Put unchanged objects, regions, background, layout, and composition only in preserve[], not in edits[].
- The prompt field must be one clean instruction for an image model: no markdown, no schema terms, no role inventory, no analysis.
{fewshot_example}
Now do the same for this request.

Instruction: {instruction}"""


def build(seed: int) -> dict:
    reference_note = " plus image2 (a reference image - give it a role and use reference_slots on any edits[] entry that draws on it)"
    reference_role_note = " and image2 (pick the best-fitting role). Cite image2 in reference_slots for the edit that uses it"
    prompt_text = GUIDANCE_FEWSHOT.format(
        reference_note=reference_note,
        reference_role_note=reference_role_note,
        fewshot_example=FEWSHOT_EXAMPLE,
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


if __name__ == "__main__":
    seeds = [int(s) for s in sys.argv[1:]] or [99002, 99003, 99004, 99005, 99006]
    results = []
    for seed in seeds:
        graph = build(seed)
        with open(f"tests/router/runs/AFRfs_{seed}.graph.json", "w", encoding="utf-8") as f:
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

    with open("tests/router/runs/AFRfs_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
