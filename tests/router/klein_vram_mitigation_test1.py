"""
Tests whether a VRAM_Debug node (KJNodes, already installed and used in the
user's own Z-Image Base workflows) reduces the cold-start VRAM squeeze found
in klein_vram_test1.py's base_no_mask_save test (637 MiB free, n=1).

Root-cause investigation first (not guessed): correlated
tests/router/runs/vram_log_kleinvram1_base_no_mask_save.csv against
G:\\ComfyUI-Easy-Install\\ComfyUI\\user\\comfyui.log's per-model load events
for that exact prompt_id (630bdd4a...). Finding: SAM3 is NOT the problem -
it loads (~2.4->7.5GB), segments, and is fully unloaded (7.5GB->2.4GB drop)
BEFORE the CLIP text encoder (Qwen3-8B, 8998MB staged) even starts loading.
The real squeeze is the CLIP->UNET transition: CLIP ramps to ~10.7GB, then
a partial drop to ~5.2GB happens right as the UNET load request fires,
suggesting ComfyUI's dynamic memory manager evicts CLIP on-demand but with
enough overlap during the handoff to set the peak (15341 MiB used, 637 MiB
free). This is consistent with PyTorch's caching allocator not releasing
freed-but-cached memory back to the pool until something forces it (e.g.
torch.cuda.empty_cache()) - not a missing unload, a missing cache flush.

Mitigation tested: insert a VRAM_Debug node (comfyui-kjnodes) between the
completed positive-conditioning chain and the sampler, with empty_cache=True
and gc_collect=True (NOT unload_all_models - that would risk unloading a
model that already started loading concurrently, forcing a wasteful
reload). VRAM_Debug's any_input/any_output pair (type *) is used purely to
force this node to run after text encoding but before the sampler/UNET
consumes its "positive" input - the same class of dependency-injection fix
this project has used before (StringSubstring in build_router_graph.py for
the E2/E3 negative-prompt ordering fix).

Not a modification of klein_test1_masked_reference.py's build() - this
script takes its graph and does graph surgery, keeping the validated test
matrix script untouched.
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
from klein_test1_masked_reference import build, PROMPT_B, REF_IMAGE_RED  # noqa: E402
from klein_vram_test1 import sample_vram  # noqa: E402 - reuse the same loop-mode sampler

SEED = 424242  # same seed as the base_no_mask_save baseline, for direct comparison


def inject_vram_debug(graph: dict, positive_node_ref: list) -> dict:
    """Insert a VRAM_Debug node between positive_node_ref and whatever consumes
    it, forcing an empty_cache+gc_collect pass after text encoding, before
    the sampler's model (UNET) input is actually needed."""
    graph["vram_debug"] = {
        "class_type": "VRAM_Debug",
        "inputs": {
            "empty_cache": True,
            "gc_collect": True,
            "unload_all_models": False,
            "any_input": positive_node_ref,
        },
    }
    return graph


def inject_pixaroma_free_vram(graph: dict, positive_node_ref: list) -> dict:
    """Insert PixaromaFreeVram (ComfyUI-Pixaroma) in the same position. Source
    read (node_free_vram.py + _free_vram_helpers.py) before use, per project
    discipline: FreeVramState's documented default ("{}" -> DEFAULT_STATE) is
    mode="all", which calls mm.unload_all_models() + gc.collect() +
    mm.soft_empty_cache(True) - the full unload VRAM_Debug's test deliberately
    avoided. Safe here because, at this point in the graph (right after text
    encoding), UNET has not been requested to load yet - unload_all_models()
    can only unload what's already loaded (CLIP, VAE), not something that
    doesn't exist yet. "value" left unwired would make the node a no-op (its
    own guard against firing when someone just drops it on a canvas to look
    at it) - wiring positive_node_ref into it is what makes it actually act.
    FreeVramState is deliberately omitted from the submitted graph so the
    node's own schema default ("{}") applies, rather than guessing a
    different explicit state."""
    graph["pixaroma_free_vram"] = {
        "class_type": "PixaromaFreeVram",
        "inputs": {
            "value": positive_node_ref,
        },
    }
    return graph


def run(label: str, mitigation: str, out_dir: Path):
    # mitigation: "none" / "vram_debug" / "pixaroma"
    assert_queue_empty()
    free()

    graph_dict = build(SEED, PROMPT_B, REF_IMAGE_RED, profile="base", include_mask_preview=False)
    graph = graph_dict["prompt"]

    if mitigation == "vram_debug":
        original_positive = graph["guider"]["inputs"]["positive"]
        graph = inject_vram_debug(graph, original_positive)
        graph["guider"]["inputs"]["positive"] = ["vram_debug", 0]
    elif mitigation == "pixaroma":
        original_positive = graph["guider"]["inputs"]["positive"]
        graph = inject_pixaroma_free_vram(graph, original_positive)
        graph["guider"]["inputs"]["positive"] = ["pixaroma_free_vram", 0]

    csv_path = out_dir / f"vram_log_mitigation1_{label}.csv"
    hist_path = out_dir / f"history_mitigation1_{label}.json"
    graph_path = out_dir / f"graph_mitigation1_{label}.json"
    graph_path.write_text(json.dumps({"prompt": graph}, indent=2, ensure_ascii=False), encoding="utf-8")

    gaps: list = []
    stop_event = threading.Event()
    sampler = threading.Thread(target=sample_vram, args=(csv_path, stop_event, gaps), daemon=True)
    sampler.start()
    time.sleep(0.3)

    t0 = time.time()
    pid = submit({"prompt": graph})
    result = poll_history(pid, timeout_s=2400)
    t1 = time.time()

    time.sleep(0.3)
    stop_event.set()
    sampler.join(timeout=3)

    hist_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = [line.strip().split(",") for line in csv_path.read_text(encoding="utf-8").splitlines()[1:] if line.strip()]
    free_mib = [int(r[2]) for r in rows if len(r) == 3]
    used_mib = [int(r[1]) for r in rows if len(r) == 3]

    outs = result.get("outputs", {})
    summary = {
        "label": label, "mitigation": mitigation, "prompt_id": pid, "seed": SEED,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
        "vram_samples": len(rows),
        "vram_used_max_mib": max(used_mib) if used_mib else None,
        "vram_free_min_mib": min(free_mib) if free_mib else None,
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    out_dir = Path("tests/router/runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    label = sys.argv[1]  # "baseline" / "mitigated" (VRAM_Debug) / "pixaroma"
    mitigation = {"baseline": "none", "mitigated": "vram_debug", "pixaroma": "pixaroma"}[label]
    run(label, mitigation=mitigation, out_dir=out_dir)
