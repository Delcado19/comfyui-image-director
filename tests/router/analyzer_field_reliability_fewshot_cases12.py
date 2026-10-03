"""
Regression check (Codex-required before any adoption decision, thread
019fd14f-0515-7a91-958a-ce162f468ce2): does the case-3-oriented few-shot
example + v3 schema-order (analyzer_field_reliability_fewshot.py) break
cases 1/2, which already worked cleanly under the router's current
baseline GUIDANCE (RESULTS_repeat_seed_cases12.md, n=5 each, no reference
image)? n=3 each, analyzer-only, no KSampler.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from analyzer_field_reliability_fewshot import GUIDANCE_FEWSHOT, FEWSHOT_EXAMPLE, MODEL_PATH, MMPROJ_PATH
from analyzer_field_reliability_v3 import edit_plan_schema_v3
from comfy_submit import submit, poll_history

CASES = {
    "case1": "Remove the beer bottle standing on top of the trash can. Keep the woman, her clothing, and everything else in the scene unchanged.",
    "case2": "Restyle the entire photo as a vintage 1970s film photograph with warm faded colors and visible film grain.",
}
EXPECTED_LOCAL = {"case1": True, "case2": False}


def build(case: str, seed: int) -> dict:
    prompt_text = GUIDANCE_FEWSHOT.format(
        reference_note="", reference_role_note="", fewshot_example=FEWSHOT_EXAMPLE,
        instruction=CASES[case],
    )
    schema = edit_plan_schema_v3(reference_count=0)
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "analyzer": {
            "class_type": "QwenVLStructuredGGUF",
            "inputs": {
                "model_path": MODEL_PATH, "mmproj_path": MMPROJ_PATH,
                "prompt": prompt_text, "json_schema": json.dumps(schema),
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
    seeds = [int(s) for s in sys.argv[2:]] or [99002, 99003, 99004]
    results = []
    for seed in seeds:
        graph = build(case, seed)
        with open(f"tests/router/runs/AFRfs12_{case}_{seed}.graph.json", "w", encoding="utf-8") as f:
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
        try:
            plan = json.loads(raw_text)
        except Exception:
            plan = {}
        row = {
            "case": case, "seed": seed, "prompt_id": pid,
            "task": plan.get("task"), "is_local_region": plan.get("is_local_region"),
            "expected_is_local_region": EXPECTED_LOCAL[case],
            "edits": plan.get("edits"), "raw": raw_text,
        }
        results.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "raw"}, indent=2))

    with open(f"tests/router/runs/AFRfs12_{case}_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
