"""
Submit one analyzer-JSON-test graph to the running ComfyUI server, poll
until done, extract PreviewAny's captured text, save it as an artifact.

No VRAM measurement here (not needed for this test - see TESTPLAN.md; VRAM
scheduling was already covered by tests/vram/combined-multiref/). Guardrails
per the joint Claude-Codex test plan: queue must be empty before submitting,
no editor/sampler stage, no global config changes, no installs.

submit()/poll_history() (the node_errors-checking HTTP layer - see
tests/lib/comfy_submit.py's docstring for why that check exists) now live
in the shared module, used by every ComfyUI-submitting test script in this
project.

Usage: python submit_and_capture.py <graph.json> <out.txt>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.comfy_submit import assert_queue_empty, poll_history, submit  # noqa: E402


if __name__ == "__main__":
    graph_path = sys.argv[1]
    out_path = sys.argv[2]

    assert_queue_empty()

    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    t0 = time.time()
    prompt_id = submit(graph)
    print(json.dumps({"event": "submitted", "prompt_id": prompt_id, "t": t0}))

    result = poll_history(prompt_id)
    t1 = time.time()

    status = result.get("status", {})
    outputs = result.get("outputs", {})

    text_out = None
    text_node_id = None
    for node_id, out in outputs.items():
        texts = out.get("text")
        if texts:
            text_out = texts[0]
            text_node_id = node_id
            break

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text_out or "")

    summary = {
        "event": "finished",
        "prompt_id": prompt_id,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": status.get("completed"),
        "status_messages": status.get("messages", []),
        "output_node_ids": list(outputs.keys()),
        "text_node_id": text_node_id,
        "text_length": len(text_out) if text_out else 0,
        "saved_to": out_path,
    }
    print(json.dumps(summary, indent=2))
