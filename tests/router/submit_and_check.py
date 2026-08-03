"""
Submit a router graph and poll for completion. submit()/poll_history() (the
node_errors-checking HTTP layer - see tests/lib/comfy_submit.py's docstring
for why that check exists) now live in the shared tests/lib/comfy_submit.py,
used by every ComfyUI-submitting test script in this project.

wait_and_report() adds router-specific hard-fail checks on top: raises if
the run didn't complete, any [ERROR] line appeared in the log during the
run, or no image output was produced - per Codex review, node_errors alone
doesn't close the gap if the caller can still misread a later empty/errored
result as a pass.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.comfy_submit import assert_queue_empty, poll_history, submit  # noqa: E402

LOG_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log"


def get_log_tail_line_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def get_new_log_lines(start_line_count):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return lines[start_line_count:]


def wait_and_report(prompt_id: str, log_start: int, timeout_s: int = 180):
    t0 = time.time()
    result = poll_history(prompt_id, timeout_s=timeout_s)
    t1 = time.time()
    new_lines = get_new_log_lines(log_start)
    errors_in_log = [ln for ln in new_lines if "[ERROR]" in ln]
    gguf_loads = [ln.strip() for ln in new_lines if "[QwenVL] Loading GGUF" in ln or "Requested to load" in ln]
    report = {
        "prompt_id": prompt_id,
        "wall_time_s": round(t1 - t0, 2),
        "status": result.get("status"),
        "outputs": result.get("outputs"),
        "log_errors": errors_in_log,
        "log_load_lines": gguf_loads,
    }

    # Codex review (2026-08-03, router-v1 thread): checking node_errors
    # at submit time is not enough - also assert the run actually
    # completed and produced an image, instead of leaving that to a
    # human eyeballing the printed report. This is the same class of
    # gap that caused the router's first submission to be misread as
    # a pass (see RESULTS_router_v1.md).
    if not result.get("status", {}).get("completed"):
        raise RuntimeError(f"Run did not complete:\n{json.dumps(report, indent=2)}")
    if errors_in_log:
        raise RuntimeError(f"[ERROR] lines in log during this run:\n{json.dumps(report, indent=2)}")
    images = [
        img
        for node_output in (result.get("outputs") or {}).values()
        for img in node_output.get("images", [])
    ]
    if not images:
        raise RuntimeError(f"No image output produced:\n{json.dumps(report, indent=2)}")
    report["images"] = images
    return report


if __name__ == "__main__":
    graph_path = sys.argv[1]
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    assert_queue_empty()

    log_start = get_log_tail_line_count()
    try:
        prompt_id = submit(graph)
    except RuntimeError as exc:
        print(f"SUBMIT FAILED: {exc}")
        sys.exit(1)

    print(json.dumps({"event": "submitted", "prompt_id": prompt_id}))
    report = wait_and_report(prompt_id, log_start)
    print(json.dumps(report, indent=2))
