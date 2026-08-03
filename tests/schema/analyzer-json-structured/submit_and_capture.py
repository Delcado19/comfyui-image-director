"""Submit one structured-analyzer graph to ComfyUI's real queue, poll, capture PreviewAny's text output."""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"


def get_queue():
    with urllib.request.urlopen(f"{BASE}/queue", timeout=15) as resp:
        return json.loads(resp.read())


def post_prompt(graph: dict) -> str:
    data = json.dumps(graph).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    return body["prompt_id"]


def poll_history(prompt_id: str, timeout_s: int = 120) -> dict:
    start = time.time()
    while time.time() - start < timeout_s:
        with urllib.request.urlopen(f"{BASE}/history/{prompt_id}", timeout=15) as resp:
            hist = json.loads(resp.read())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(0.5)
    raise TimeoutError(f"prompt {prompt_id} did not finish within {timeout_s}s")


if __name__ == "__main__":
    graph_path = sys.argv[1]
    out_path = sys.argv[2]

    q = get_queue()
    pending = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
    if pending:
        print(json.dumps({"event": "abort", "reason": "queue not empty", "queue": q}))
        sys.exit(2)

    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    t0 = time.time()
    prompt_id = post_prompt(graph)
    print(json.dumps({"event": "submitted", "prompt_id": prompt_id, "t": t0}))

    result = poll_history(prompt_id)
    t1 = time.time()

    status = result.get("status", {})
    outputs = result.get("outputs", {})

    text_out = None
    for node_id, out in outputs.items():
        texts = out.get("text")
        if texts:
            text_out = texts[0]
            break

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text_out or "")

    summary = {
        "event": "finished",
        "prompt_id": prompt_id,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": status.get("completed"),
        "status_messages": status.get("messages", []),
        "text_length": len(text_out) if text_out else 0,
        "saved_to": out_path,
    }
    print(json.dumps(summary, indent=2))
