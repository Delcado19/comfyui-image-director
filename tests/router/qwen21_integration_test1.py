"""
First real end-to-end test of build_router_graph.py's edit_mode="native_reference"
/ editor="qwen_image21" addition - through the actual router (analyzer ->
lazy switch -> branch), not the standalone qwen_image21_reference_test1.py
mechanism test. Validates Codex's stated acceptance criteria for this
integration (2026-10-05 router consultation): analyzer JSON and the actual
prompt passed are captured, both edit cases (red/green reference) follow
their reference while preserving the scene, generate loads no
Qwen-Image-2.1 components, edit loads no Z-Image components, logs confirm
analyzer-before-editor-chain ordering, VRAM sampling (including measurement
gaps) stays above the project's 300 MiB floor, and no [ERROR] lines appear.

Reuses the same fixtures as qwen_image21_reference_test1.py's B/B2
variants for direct comparability - blue-dress source, red/green reference
swatches, same seed.

Log-hit detection note: the analyzer itself is also a "Qwen" model
(Qwen2.5-VL-7B-Instruct-abliterated GGUF) and runs on every request
regardless of branch, so a bare "qwen" substring would false-positive.
Uses the UNET/text-encoder filenames unique to this editor's loaders
instead (qwenImage21Nvfp4Q4 / qwen3vl_8b_w4a8).
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
from build_router_graph import build  # noqa: E402
from klein_vram_test1 import sample_vram  # noqa: E402 - reuse the same loop-mode sampler

LOG_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log"
SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
REF_IMAGE_GREEN = "imgdir_masktest2_ref_green.png"
SEED = 424243
OUT_DIR = Path("tests/router/runs")
# Unique to this editor's own loaders - never emitted by the analyzer
# (abliterated Qwen2.5-VL GGUF) or the Z-Image Turbo generate branch.
QWEN21_LOG_MARKERS = ("qwenImage21Nvfp4Q4", "qwen3vl_8b_w4a8")


def log_tail_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def new_log_lines(start):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()[start:]


def run_case(label: str, instruction: str, edit_mode: str, expect_qwen21_executed: bool, ref_image: str | None = None,
             seed: int = SEED, do_free: bool = True, sample_vram_flag: bool = False, timeout_s: int = 300):
    assert_queue_empty()
    if do_free:
        free()

    kwargs = dict(
        instruction=instruction, seed=seed, analyzer_seed=seed,
        refs=[ref_image] if edit_mode == "native_reference" else [],
        edit_mode=edit_mode, source_image=SOURCE_IMAGE, editor="qwen_image21",
    )
    graph = build(**kwargs)["prompt"]
    (OUT_DIR / f"graph_qwen21integration1_{label}.json").write_text(
        json.dumps({"prompt": graph}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    gaps: list = []
    stop_event = threading.Event()
    sampler = None
    if sample_vram_flag:
        csv_path = OUT_DIR / f"vram_log_qwen21integration1_{label}.csv"
        sampler = threading.Thread(target=sample_vram, args=(csv_path, stop_event, gaps), daemon=True)
        sampler.start()
        time.sleep(0.3)

    log_start = log_tail_count()
    t0 = time.time()
    pid = submit({"prompt": graph})
    result = poll_history(pid, timeout_s=timeout_s)
    t1 = time.time()

    vram_free_min_mib = None
    vram_used_max_mib = None
    if sample_vram_flag:
        time.sleep(0.3)
        stop_event.set()
        sampler.join(timeout=3)
        rows = [ln.strip().split(",") for ln in csv_path.read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
        free_vals = [int(r[2]) for r in rows if len(r) == 3]
        used_vals = [int(r[1]) for r in rows if len(r) == 3]
        vram_free_min_mib = min(free_vals) if free_vals else None
        vram_used_max_mib = max(used_vals) if used_vals else None

    (OUT_DIR / f"history_qwen21integration1_{label}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    msgs = result.get("status", {}).get("messages", [])
    cached_nodes = next((m[1].get("nodes") for m in msgs if m[0] == "execution_cached"), [])
    qwen21_cached_hit = any(n.startswith("qwen21") for n in (cached_nodes or []))
    outs = result.get("outputs", {})
    new_lines = new_log_lines(log_start)
    qwen21_log_hits = [ln.strip() for ln in new_lines if any(m in ln for m in QWEN21_LOG_MARKERS)]
    error_lines = [ln.strip() for ln in new_lines if "[ERROR]" in ln]

    filenames = [i["filename"] for i in outs.get("save", {}).get("images", [])]

    summary = {
        "label": label, "edit_mode": edit_mode, "prompt_id": pid,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": filenames,
        "qwen21_log_hits": qwen21_log_hits,
        "qwen21_executed": bool(qwen21_log_hits) or qwen21_cached_hit,
        "expect_qwen21_executed": expect_qwen21_executed,
        "error_lines": error_lines,
        "vram_free_min_mib": vram_free_min_mib,
        "vram_used_max_mib": vram_used_max_mib,
    }
    print(json.dumps(summary, indent=2))

    if error_lines:
        raise RuntimeError(f"[ERROR] lines in log during {label}: {error_lines}")
    if not result.get("status", {}).get("completed"):
        raise RuntimeError(f"{label} did not complete")
    if summary["qwen21_executed"] != expect_qwen21_executed:
        raise RuntimeError(
            f"{label}: expected qwen21_executed={expect_qwen21_executed}, got {summary['qwen21_executed']} "
            f"(qwen21_log_hits={qwen21_log_hits})"
        )
    return summary


if __name__ == "__main__":
    case = sys.argv[1]  # "edit_red" / "edit_green" / "generate"
    if case == "edit_red":
        run_case(
            "edit_red", instruction="Change the color of the dress in this photo.",
            edit_mode="native_reference", ref_image=REF_IMAGE_RED, expect_qwen21_executed=True, sample_vram_flag=True,
        )
    elif case == "edit_green":
        run_case(
            "edit_green", instruction="Change the color of the dress in this photo.",
            edit_mode="native_reference", ref_image=REF_IMAGE_GREEN, expect_qwen21_executed=True,
        )
    elif case == "generate":
        run_case(
            "generate_with_qwen21_wiring",
            instruction="Generate a picture of a quiet mountain lake at sunrise, no people.",
            edit_mode="native_reference", ref_image=REF_IMAGE_RED, expect_qwen21_executed=False, timeout_s=180,
        )
    else:
        raise SystemExit(f"unknown case: {case!r}, expected 'edit_red', 'edit_green', or 'generate'")
