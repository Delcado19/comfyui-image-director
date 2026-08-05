"""
Repeat-seed check for content-quality cases 1 and 2 (RESULTS_content_quality.md),
which so far only ran at n=1 - a standing open item ("Remaining open items"/
"What this does not settle"). Analyzer-only (no KSampler/image generation),
reusing the cheap no-render harness from analyzer_field_reliability.py, now
also exercising the just-added validate_edit_plan(check_consistency=True)
(RESULTS_consistency_check.md) on cases that don't involve a reference image,
to check it doesn't false-positive and to see whether the already-known
"entire image"/"full image" placeholder-collapse pattern (documented for
case 1 at n=1) is a one-off or reproducible.

Both cases use reference_count=0 (no reference image), current router
GUIDANCE/schema (build_router_graph.py's exact wording), same source photo
IMG_7148.jpg as case 3.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director")
from image_director.edit_plan_schema import edit_plan_schema, validate_edit_plan

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf"

# Same wording as build_router_graph.py's GUIDANCE (no reference image -> "").
GUIDANCE = """You are creating a structured plan for an image generation/editing pipeline. schema_version is always "1.0". If this is a text-to-image request unrelated to the attached image(s), use task="generate" - ignore the attached image(s) entirely in that case. If the request modifies the attached image, use task="edit": set is_local_region to true only if just one specific subject/region should change and everything else must stay the same (false if the whole image is being transformed/restyled), list "images" with image1 (role "source"), describe the needed edit(s), and list what must be preserved. For edits[]: only list things that actually change; use subject "entire image"/region "full image" only when no more specific subject exists; the prompt field must be one clean instruction for an image model, no markdown or commentary.

Instruction: {instruction}"""

CASES = {
    "case1": "Remove the beer bottle standing on top of the trash can. Keep the woman, her clothing, and everything else in the scene unchanged.",
    "case2": "Restyle the entire photo as a vintage 1970s film photograph with warm faded colors and visible film grain.",
}
# case2 is a whole-image restyle - "entire image"/"full image" is the
# schema's own CORRECT usage there (no more specific subject exists), so
# don't run the placeholder-overuse/consistency scoring against it the same
# way as case1/case3 (a local edit). Tracked, not scored as failure.
EXPECTED_LOCAL = {"case1": True, "case2": False}


def build(case: str, seed: int) -> dict:
    schema = edit_plan_schema(source_image=True, reference_count=0)
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "analyzer": {
            "class_type": "QwenVLStructuredGGUF",
            "inputs": {
                "model_path": MODEL_PATH, "mmproj_path": MMPROJ_PATH,
                "prompt": GUIDANCE.format(instruction=CASES[case]), "json_schema": json.dumps(schema),
                "max_tokens": 512, "temperature": 0.1, "top_p": 0.9,
                "repetition_penalty": 1.2, "seed": seed, "ctx": 8192,
                "gpu_layers": -1, "keep_model_loaded": False,
                "free_vram_before_load": True,
                "image": ["src", 0],
            },
        },
        "plan_preview": {"class_type": "PreviewAny", "inputs": {"source": ["analyzer", 0]}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    case = sys.argv[1]
    seeds = [int(s) for s in sys.argv[2:]] or [99002, 99003, 99004, 99005, 99006]
    results = []
    for seed in seeds:
        graph = build(case, seed)
        with open(f"tests/router/runs/AFR12_{case}_{seed}.graph.json", "w", encoding="utf-8") as f:
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

        errors_structural = validate_edit_plan(raw_text or "", {"image1"})
        errors_consistency = validate_edit_plan(raw_text or "", {"image1"}, check_consistency=True)
        try:
            plan = json.loads(raw_text)
        except Exception:
            plan = {}
        row = {
            "case": case, "seed": seed, "prompt_id": pid,
            "task": plan.get("task"), "is_local_region": plan.get("is_local_region"),
            "expected_is_local_region": EXPECTED_LOCAL[case],
            "edits": plan.get("edits"),
            "structural_errors": errors_structural,
            "consistency_errors": [e for e in errors_consistency if e not in errors_structural],
            "raw": raw_text,
        }
        results.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "raw"}, indent=2))

    with open(f"tests/router/runs/AFR12_{case}_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
