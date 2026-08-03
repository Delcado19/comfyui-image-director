"""
Submit a pre-built API-format graph to the running ComfyUI server and poll
until it finishes, printing a small JSON status line ComfyUI itself
reports (no VRAM measurement here - that is done by a separate nvidia-smi
loop started/stopped around this script by the caller).

submit()/poll_history() (the node_errors-checking HTTP layer - see
tests/lib/comfy_submit.py's docstring for why that check exists) now live
in the shared module, used by every ComfyUI-submitting test script in this
project.

Usage: python submit_and_monitor.py <graph.json>
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.comfy_submit import poll_history, submit  # noqa: E402

COMFY_OUTPUT_DIR = r"E:\AI_Art"


if __name__ == "__main__":
    graph_path = sys.argv[1]
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    t0 = time.time()
    prompt_id = submit(graph)
    print(json.dumps({"event": "submitted", "prompt_id": prompt_id, "t": t0}))

    result = poll_history(prompt_id, timeout_s=240)  # was this script's own default before consolidation
    t1 = time.time()

    status = result.get("status", {})
    node_errors = result.get("status", {}).get("messages", [])
    outputs = result.get("outputs", {})

    # Criterion 6: confirm SaveImage actually wrote a real file, not just
    # that ComfyUI reported a node output dict.
    save_files = []
    for node_id, out in outputs.items():
        for img in out.get("images", []):
            fname = img.get("filename")
            subfolder = img.get("subfolder", "")
            full = os.path.join(COMFY_OUTPUT_DIR, subfolder, fname) if fname else None
            size = os.path.getsize(full) if full and os.path.exists(full) else None
            save_files.append({"node_id": node_id, "filename": fname, "path": full, "size_bytes": size})

    summary = {
        "event": "finished",
        "prompt_id": prompt_id,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": status.get("completed"),
        "status_messages": node_errors,
        "output_node_ids": list(outputs.keys()),
        "save_image_files": save_files,
    }
    print(json.dumps(summary, indent=2))
