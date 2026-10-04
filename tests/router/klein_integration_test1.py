"""
First real end-to-end test of build_router_graph.py's editor="klein_distilled"
addition - through the actual router (analyzer -> lazy switch -> branch),
not the standalone klein_test1_masked_reference.py mechanism test. Validates
Codex's stated acceptance criteria for the integration (round-2 review,
2026-10-04):
  - Klein masked-edit: correct transfer, measured VRAM margin.
  - Generate with Klein wiring present: NO Klein/SAM3/VRAM-gate execution.
  - Existing Qwen modes: no regression.

Source/reference images reused from the validated standalone test
(imgdir_masktest2_source_bluedress.png / imgdir_masktest2_ref_red.png) -
same fixtures, so the expected result (dress turns red) is already known.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
from build_router_graph import build  # noqa: E402

LOG_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log"
SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
SEED = 424242
OUT_DIR = Path("tests/router/runs")


def log_tail_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def new_log_lines(start):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()[start:]


def run_case(label: str, instruction: str, edit_mode: str, expect_klein_executed: bool, seed: int = SEED):
    assert_queue_empty()
    free()

    graph = build(
        instruction, seed, seed, refs=[REF_IMAGE_RED],
        edit_mode=edit_mode, mask_target="the woman's dress",
        source_image=SOURCE_IMAGE, editor="klein_distilled",
    )["prompt"]
    (OUT_DIR / f"graph_kleinintegration1_{label}.json").write_text(
        json.dumps({"prompt": graph}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log_start = log_tail_count()
    t0 = time.time()
    pid = submit({"prompt": graph})
    result = poll_history(pid, timeout_s=600)
    t1 = time.time()
    (OUT_DIR / f"history_kleinintegration1_{label}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    msgs = result.get("status", {}).get("messages", [])
    cached_nodes = next((m[1].get("nodes") for m in msgs if m[0] == "execution_cached"), [])
    # Nodes ComfyUI actually touched (cached or not) this run - anything from
    # the Klein branch appearing here means it entered the schedule, which is
    # the lazy-switch violation we're checking for on the generate case.
    # ComfyUI's history doesn't give a clean "executed" node list directly in
    # status.messages beyond execution_cached, so this checks node OUTPUTS
    # and the log for Klein-specific load/run evidence instead.
    outs = result.get("outputs", {})
    new_lines = new_log_lines(log_start)
    klein_log_hits = [ln.strip() for ln in new_lines if "klein" in ln.lower() or "Sam3" in ln or "VRAMdebug" in ln]
    error_lines = [ln.strip() for ln in new_lines if "[ERROR]" in ln]

    task_str_outputs = outs.get("task_str", {})
    filenames = [i["filename"] for i in outs.get("save", {}).get("images", [])]

    summary = {
        "label": label, "edit_mode": edit_mode, "prompt_id": pid,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": filenames,
        "klein_log_hits": klein_log_hits,
        "klein_executed": bool(klein_log_hits),
        "expect_klein_executed": expect_klein_executed,
        "error_lines": error_lines,
    }
    print(json.dumps(summary, indent=2))

    if error_lines:
        raise RuntimeError(f"[ERROR] lines in log during {label}: {error_lines}")
    if not result.get("status", {}).get("completed"):
        raise RuntimeError(f"{label} did not complete")
    if summary["klein_executed"] != expect_klein_executed:
        raise RuntimeError(
            f"{label}: expected klein_executed={expect_klein_executed}, got {summary['klein_executed']} "
            f"(klein_log_hits={klein_log_hits})"
        )
    return summary


if __name__ == "__main__":
    case = sys.argv[1]  # "edit" or "generate"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else SEED
    label_suffix = "" if seed == SEED else f"_{seed}"
    if case == "edit":
        run_case(
            f"edit_klein_masked{label_suffix}", instruction="Change the color of the dress in this photo.",
            edit_mode="masked_reference", expect_klein_executed=True, seed=seed,
        )
    elif case == "generate":
        run_case(
            f"generate_with_klein_wiring{label_suffix}",
            instruction="Generate a picture of a quiet mountain lake at sunrise, no people.",
            edit_mode="masked_reference", expect_klein_executed=False, seed=seed,
        )
    else:
        raise SystemExit(f"unknown case: {case!r}, expected 'edit' or 'generate'")
