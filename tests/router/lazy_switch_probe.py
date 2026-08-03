"""
Smallest-useful-test for the router's core mechanism: does ComfyUI's lazy
evaluation (via "easy ifElse", ComfyUI-Easy-Use) actually skip the ENTIRE
unused branch's upstream chain, or just the final node's read of that input?

Verified via source reading (comfy_execution/graph.py's TopologicalSort.
add_node(include_lazy=False) skips lazy-input upstream chains when building
the initial pending-node set; execution.py's check_lazy_status handling only
pulls in the actually-needed branch via make_input_strong_link) and via
Codex's independent trace through the same files, reaching the same
conclusion (see comfyui-image-director's Codex thread). This test verifies
it empirically, not just from source.

Design: two branches with genuinely different, externally observable cost -
LoadImage alone prints nothing distinctive to ComfyUI's log (checked: a
prior LoadImage-only run left no trace), so it can't prove non-execution by
itself. Branch "true" is a near-instant PrimitiveString (no loading, no
log line, output_node=False). Branch "false" is the actual
AILab_QwenVL_GGUF_Advanced analyzer (several seconds, prints a distinctive
"[QwenVL] Loading GGUF: ..." line, keep_model_loaded=False). Exactly one
PreviewAny after the switch - per Codex's warning, no OUTPUT_NODE=True
inside either branch (that would force it to execute regardless of the
switch, since ComfyUI treats output nodes as execution roots).

Run twice (boolean=true, then boolean=false) and check: (a) wall time,
(b) whether "[QwenVL] Loading GGUF" appears in the comfyui.log lines
written during that specific run's time window, (c) the actual output
text. If laziness works, the true run should be near-instant with no GGUF
loading log line, and the false run should take several seconds with the
GGUF loading log line present.
"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
LOG_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log"
CLIP_MODEL_NAME = "Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"


def build(boolean: bool, seed: int) -> dict:
    return {
        "prompt": {
            "1": {"class_type": "PrimitiveString", "inputs": {"value": "CHEAP_TRUE_BRANCH_MARKER"}},
            "2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_multitest_1_star.png"}},
            "3": {
                "class_type": "AILab_QwenVL_GGUF_Advanced",
                "inputs": {
                    "model_name": CLIP_MODEL_NAME,
                    "device": "auto",
                    "preset_prompt": "\U0001f5bc\ufe0f Detailed Description",
                    "custom_prompt": "Describe the shape and color in one short sentence.",
                    "max_tokens": 100,
                    "temperature": 0.6,
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
                    "image": ["2", 0],
                },
            },
            "4": {
                "class_type": "easy ifElse",
                "inputs": {"boolean": boolean, "on_true": ["1", 0], "on_false": ["3", 0]},
            },
            "5": {"class_type": "PreviewAny", "inputs": {"source": ["4", 0]}},
        }
    }


def get_log_tail_line_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def get_new_log_lines(start_line_count):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return lines[start_line_count:]


def run_case(boolean: bool, seed: int):
    log_start = get_log_tail_line_count()
    graph = build(boolean, seed)
    data = json.dumps(graph).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/prompt", data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        prompt_id = json.loads(r.read())["prompt_id"]

    while time.time() - t0 < 90:
        with urllib.request.urlopen(f"{BASE}/history/{prompt_id}", timeout=15) as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            t1 = time.time()
            result = hist[prompt_id]
            text_out = None
            for out in result.get("outputs", {}).values():
                if "text" in out:
                    text_out = out["text"][0]
            new_lines = get_new_log_lines(log_start)
            gguf_loaded = any("[QwenVL] Loading GGUF" in line for line in new_lines)
            return {
                "prompt_id": prompt_id,
                "boolean": boolean,
                "wall_time_s": round(t1 - t0, 2),
                "gguf_load_line_seen": gguf_loaded,
                "text_output": text_out,
                "status_completed": result.get("status", {}).get("completed"),
            }
        time.sleep(0.3)
    raise TimeoutError(f"{prompt_id} did not finish in time")


if __name__ == "__main__":
    boolean = sys.argv[1] == "true"
    seed = int(sys.argv[2])
    print(json.dumps(run_case(boolean, seed), indent=2))
