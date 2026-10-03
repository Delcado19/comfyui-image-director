"""
Analyzer-only reliability check (Codex-designed, thread
019fd14f-0515-7a91-958a-ce162f468ce2), no image generation / no KSampler.

Question: after two failed prompt-level fixes for case 3's "background"-word
bleed (RESULTS_ab_background_word.md, RESULTS_ab_negative_prompt.md), is a
deterministic-prompt-construction approach (building the text fed to
TextEncodeQwenImageEditPlus from edits[]/preserve[] instead of the analyzer's
free-text prompt field) worth building? Only if the analyzer's word choices
inside the *structured* fields (edits[].subject/region, preserve[]) are more
reliable than inside free prose - otherwise the same failure mode just moves.

This script only calls QwenVLStructuredGGUF (via the same wiring
build_router_graph.py uses for the analyzer, reference_count=1) and captures
the raw JSON through PreviewAny - never reaches KSampler, so it's cheap and
fast (no UNet/VAE load).

Same instruction/images as RESULTS_content_quality.md's case 3:
IMG_7148.jpg + imgdir_test_ref2.png, "Change the color of the woman's
leather dress to match the color shown in the reference image."

Scoring per sample (Codex's checklist):
- task == "edit"
- is_local_region == true
- exactly one edit targets the dress/garment (not background/scene)
- edits[].reference_slots == ["image2"]
- edits[].subject / region not in {"background","scene","environment",
  "entire image","full image"}
- prompt field flagged separately for whether it contains "background"
  (preserve[] containing "background" is NOT counted as a failure - the
  editor could reasonably be told to *keep* the background, that's a
  different role than "prompt describes the reference as a background")
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director")
from image_director.edit_plan_schema import edit_plan_schema

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf"

GUIDANCE = """You are creating a structured plan for an image generation/editing pipeline. schema_version is always "1.0". If this is a text-to-image request unrelated to the attached image(s), use task="generate" - ignore the attached image(s) entirely in that case. If the request modifies the attached image, use task="edit": set is_local_region to true only if just one specific subject/region should change and everything else must stay the same (false if the whole image is being transformed/restyled), list "images" with image1 (role "source") plus image2 (a reference image - give it a role and use reference_slots on any edits[] entry that draws on it), describe the needed edit(s), and list what must be preserved. For edits[]: only list things that actually change; use subject "entire image"/region "full image" only when no more specific subject exists; the prompt field must be one clean instruction for an image model, no markdown or commentary.

Instruction: Change the color of the woman's leather dress to match the color shown in the reference image."""

SCENE_WORDS = {"background", "scene", "environment", "entire image", "full image"}


def build(seed: int) -> dict:
    schema = edit_plan_schema(source_image=True, reference_count=1)
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "analyzer": {
            "class_type": "QwenVLStructuredGGUF",
            "inputs": {
                "model_path": MODEL_PATH, "mmproj_path": MMPROJ_PATH,
                "prompt": GUIDANCE, "json_schema": json.dumps(schema),
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
        with open(f"tests/router/runs/AFR_{seed}.graph.json", "w", encoding="utf-8") as f:
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

    with open("tests/router/runs/AFR_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
