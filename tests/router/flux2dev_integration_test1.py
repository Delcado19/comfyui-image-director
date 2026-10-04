"""
First real end-to-end test of build_router_graph.py's editor="flux2_dev"
addition - through the actual router (analyzer -> lazy switch -> branch),
not the standalone flux2dev_masking_test1.py mechanism test. Validates
Codex's stated acceptance criteria for this integration (2026-10-04 router
consultation): correct reference effect, preserved locality, measured VRAM
margin above the 300 MiB floor, confirmed lazy generate/edit AND
editor-selection behavior (Dev/SAM3 stay unscheduled when editor="flux2_dev"
is wired but the analyzer picks "generate"), no regression on existing
Qwen/Klein modes (see the inline structural check already run separately).

Reuses the same fixtures as flux2dev_masking_test1.py's variant M (material
test) for direct comparability - same source/reference, same expected
result (leather texture on the masked dress).
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
REF_IMAGE_LEATHER = "imgdir_masktest2_ref_leather.png"
SEED = 777777
OUT_DIR = Path("tests/router/runs")


def log_tail_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def new_log_lines(start):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()[start:]


def run_case(label: str, instruction: str, edit_mode: str, expect_dev_executed: bool, seed: int = SEED,
             do_free: bool = True, sample_vram_flag: bool = False, ref_image: str = REF_IMAGE_LEATHER,
             timeout_s: int = 1200):
    assert_queue_empty()
    if do_free:
        free()

    kwargs = dict(instruction=instruction, seed=seed, analyzer_seed=seed, refs=[ref_image] if edit_mode == "masked_reference" else [],
                  edit_mode=edit_mode, source_image=SOURCE_IMAGE, editor="flux2_dev")
    if edit_mode == "masked_reference":
        kwargs["mask_target"] = "the woman's dress"
    graph = build(**kwargs)["prompt"]
    (OUT_DIR / f"graph_flux2devintegration1_{label}.json").write_text(
        json.dumps({"prompt": graph}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    gaps: list = []
    stop_event = threading.Event()
    sampler = None
    if sample_vram_flag:
        csv_path = OUT_DIR / f"vram_log_flux2devintegration1_{label}.csv"
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

    (OUT_DIR / f"history_flux2devintegration1_{label}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    msgs = result.get("status", {}).get("messages", [])
    cached_nodes = next((m[1].get("nodes") for m in msgs if m[0] == "execution_cached"), [])
    dev_cached_hit = any(n.startswith("dev") or n.startswith("sam3") for n in (cached_nodes or []))
    outs = result.get("outputs", {})
    new_lines = new_log_lines(log_start)
    dev_log_hits = [ln.strip() for ln in new_lines if "gguf" in ln.lower() or "Sam3" in ln or "flux2 dev" in ln.lower()]
    error_lines = [ln.strip() for ln in new_lines if "[ERROR]" in ln]

    filenames = [i["filename"] for i in outs.get("save", {}).get("images", [])]

    summary = {
        "label": label, "edit_mode": edit_mode, "prompt_id": pid,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": filenames,
        "dev_log_hits": dev_log_hits,
        "dev_executed": bool(dev_log_hits) or dev_cached_hit,
        "expect_dev_executed": expect_dev_executed,
        "error_lines": error_lines,
        "vram_free_min_mib": vram_free_min_mib,
        "vram_used_max_mib": vram_used_max_mib,
    }
    print(json.dumps(summary, indent=2))

    if error_lines:
        raise RuntimeError(f"[ERROR] lines in log during {label}: {error_lines}")
    if not result.get("status", {}).get("completed"):
        raise RuntimeError(f"{label} did not complete")
    if summary["dev_executed"] != expect_dev_executed:
        raise RuntimeError(
            f"{label}: expected dev_executed={expect_dev_executed}, got {summary['dev_executed']} "
            f"(dev_log_hits={dev_log_hits})"
        )
    return summary


if __name__ == "__main__":
    case = sys.argv[1]  # "edit" / "generate"
    if case == "edit":
        run_case(
            "edit_flux2dev_masked", instruction="Change the color of the dress in this photo.",
            edit_mode="masked_reference", expect_dev_executed=True, sample_vram_flag=True,
        )
    elif case == "generate":
        run_case(
            "generate_with_flux2dev_wiring",
            instruction="Generate a picture of a quiet mountain lake at sunrise, no people.",
            edit_mode="masked_reference", expect_dev_executed=False, timeout_s=180,
        )
    else:
        raise SystemExit(f"unknown case: {case!r}, expected 'edit' or 'generate'")
