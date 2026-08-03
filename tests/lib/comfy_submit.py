"""
Shared ComfyUI /prompt submission + /history polling helper.

Extracted after the router's first submission silently "succeeded": /prompt
returned a prompt_id with HTTP 200, but the response body's node_errors
field held a real validation rejection ("Value not in list") that only a
body-content check - not an HTTP-status check - would catch (see
tests/router/RESULTS_router_v1.md). Every ComfyUI-submitting test script in
this project had its own copy of this same post_prompt/poll_history logic,
none of them checking node_errors; consolidated here per Codex review so
the fix lives in one place instead of four.
"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8188"


def submit(graph: dict, base: str = BASE) -> str:
    data = json.dumps(graph).encode("utf-8")
    req = urllib.request.Request(f"{base}/prompt", data=data, headers={"Content-Type": "application/json"})
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


def poll_history(prompt_id: str, base: str = BASE, timeout_s: int = 180) -> dict:
    start = time.time()
    while time.time() - start < timeout_s:
        with urllib.request.urlopen(f"{base}/history/{prompt_id}", timeout=15) as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(0.5)
    raise TimeoutError(f"{prompt_id} did not finish within {timeout_s}s")


def get_queue(base: str = BASE) -> dict:
    with urllib.request.urlopen(f"{base}/queue", timeout=15) as r:
        return json.loads(r.read())


def assert_queue_empty(base: str = BASE) -> None:
    q = get_queue(base)
    pending = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
    if pending:
        raise RuntimeError(f"queue not empty: {json.dumps(q)}")
