"""
Submit a router graph and poll for completion. Unlike earlier scripts this
session, explicitly checks the /prompt response body for "node_errors" -
the router_generate.graph.json incident showed that ComfyUI can return
prompt_id successfully (no HTTP error) while still rejecting specific nodes
("Failed to validate prompt for output save", "Output will be ignored"),
silently producing an empty-outputs "success". Checking only the HTTP
status code was not sufficient - this checks the actual response body.

wait_and_report() also hard-fails (raises) if the run didn't complete, any
[ERROR] line appeared in the log during the run, or no image output was
produced - per Codex review, node_errors alone doesn't close the gap if the
caller can still misread a later empty/errored result as a pass.
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8188"
LOG_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log"


def get_log_tail_line_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def get_new_log_lines(start_line_count):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return lines[start_line_count:]


def submit(graph: dict):
    data = json.dumps(graph).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        raise RuntimeError(f"HTTP {e.code}: {json.dumps(body, indent=2)}")

    node_errors = body.get("node_errors") or {}
    if node_errors:
        raise RuntimeError(f"Validation errors in response body:\n{json.dumps(node_errors, indent=2)}")
    if "prompt_id" not in body:
        raise RuntimeError(f"No prompt_id in response, unexpected shape: {json.dumps(body, indent=2)}")
    return body["prompt_id"]


def wait_and_report(prompt_id: str, log_start: int, timeout_s: int = 180):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        with urllib.request.urlopen(f"{BASE}/history/{prompt_id}", timeout=15) as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            t1 = time.time()
            result = hist[prompt_id]
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
        time.sleep(0.5)
    raise TimeoutError(f"{prompt_id} did not finish within {timeout_s}s")


if __name__ == "__main__":
    graph_path = sys.argv[1]
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    with urllib.request.urlopen(f"{BASE}/queue", timeout=10) as r:
        q = json.loads(r.read())
    if q.get("queue_running") or q.get("queue_pending"):
        print(json.dumps({"event": "abort", "reason": "queue not empty"}))
        sys.exit(2)

    log_start = get_log_tail_line_count()
    try:
        prompt_id = submit(graph)
    except RuntimeError as exc:
        print(f"SUBMIT FAILED: {exc}")
        sys.exit(1)

    print(json.dumps({"event": "submitted", "prompt_id": prompt_id}))
    report = wait_and_report(prompt_id, log_start)
    print(json.dumps(report, indent=2))
