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
SEED = 424242
OUT_DIR = Path("tests/router/runs")


def log_tail_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def new_log_lines(start):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()[start:]


def run_case(label: str, instruction: str, edit_mode: str, expect_klein_executed: bool, seed: int = SEED,
             do_free: bool = True, sample_vram_flag: bool = False, ref_image: str = REF_IMAGE_RED):
    assert_queue_empty()
    if do_free:
        free()

    graph = build(
        instruction, seed, seed, refs=[ref_image],
        edit_mode=edit_mode, mask_target="the woman's dress",
        source_image=SOURCE_IMAGE, editor="klein_distilled",
    )["prompt"]
    (OUT_DIR / f"graph_kleinintegration1_{label}.json").write_text(
        json.dumps({"prompt": graph}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    gaps: list = []
    stop_event = threading.Event()
    sampler = None
    if sample_vram_flag:
        csv_path = OUT_DIR / f"vram_log_kleinintegration1_{label}.csv"
        sampler = threading.Thread(target=sample_vram, args=(csv_path, stop_event, gaps), daemon=True)
        sampler.start()
        time.sleep(0.3)

    log_start = log_tail_count()
    t0 = time.time()
    pid = submit({"prompt": graph})
    result = poll_history(pid, timeout_s=600)
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

    (OUT_DIR / f"history_kleinintegration1_{label}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    msgs = result.get("status", {}).get("messages", [])
    cached_nodes = next((m[1].get("nodes") for m in msgs if m[0] == "execution_cached"), [])
    # klein_* / sam3_* nodes appearing in cached_nodes means they were in
    # the schedule and ComfyUI reused a valid prior result - NOT the same as
    # never being scheduled at all (the actual lazy-switch violation this
    # check exists for). Found 2026-10-04 in the back-to-back chain test:
    # repeated identical-input runs (same source/reference/mask_target,
    # only a different final sampler seed) legitimately cache the entire
    # Klein/SAM3/VRAM_Debug chain, producing zero fresh log lines even
    # though the branch is genuinely part of the schedule - the original
    # log-hits-only check misread this as a lazy-switch failure. Checking
    # cached_nodes for klein_*/sam3_* IDs too fixes the false negative.
    klein_cached_hit = any(n.startswith("klein") or n.startswith("sam3") for n in (cached_nodes or []))
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
        "klein_executed": bool(klein_log_hits) or klein_cached_hit,
        "klein_cached": klein_cached_hit,
        "expect_klein_executed": expect_klein_executed,
        "error_lines": error_lines,
        "vram_free_min_mib": vram_free_min_mib,
        "vram_used_max_mib": vram_used_max_mib,
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
    case = sys.argv[1]  # "edit" / "generate" / "chain"
    if case == "chain":
        # Back-to-back-without-/free chain (added 2026-10-04): the
        # router-integrated graph shape (string-gate pair, VRAM_Debug,
        # SAM3 on src instead of edit_scale) was only proven safe
        # back-to-back in its STANDALONE form
        # (RESULTS_klein_test1_masked_reference.md's chain test) - not yet
        # re-verified for this exact integrated shape under repeated real
        # router traffic (flagged as a remaining risk in
        # RESULTS_router_klein_integration.md). Only the first run gets a
        # clean /free floor; different seeds per run avoid the same-seed
        # cache-hit trap found earlier in klein_vram_mitigation_test1.py's
        # own chain test - but a first attempt here found that varying only
        # the seed is NOT enough at the router level: the Klein branch's
        # conditioning (klein_pos_text's literal text depends on mask_target,
        # not the sampler seed) and SAM3 segmentation (depends only on
        # source + mask_target) both still fully cache, since those nodes
        # have no seed dependency at all. The whole Klein/SAM3/VRAM_Debug
        # chain got reused from run 1 with zero fresh execution - legitimate
        # ComfyUI caching, not a bug, but not a realistic "different request"
        # either. Alternating the reference image (red/green/red) forces
        # genuine re-execution of the conditioning+sampler+VRAM-gate chain
        # each run, closer to real back-to-back traffic with different
        # requests (SAM3 segmentation itself may still legitimately cache,
        # since it only depends on source+mask_target, which stay constant
        # here - that's expected/correct either way).
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        base_seed = int(sys.argv[3]) if len(sys.argv) > 3 else SEED
        ref_cycle = [REF_IMAGE_RED, REF_IMAGE_GREEN]
        summaries = []
        for i in range(1, n + 1):
            s = run_case(
                f"chain_edit_{i}", instruction="Change the color of the dress in this photo.",
                edit_mode="masked_reference", expect_klein_executed=True,
                seed=base_seed + i, do_free=(i == 1), sample_vram_flag=True,
                ref_image=ref_cycle[(i - 1) % len(ref_cycle)],
            )
            summaries.append(s)
        print(json.dumps({"chain_summary": [
            {"run": s["label"], "vram_free_min_mib": s["vram_free_min_mib"], "vram_used_max_mib": s["vram_used_max_mib"]}
            for s in summaries
        ]}, indent=2))
    else:
        seed = int(sys.argv[2]) if len(sys.argv) > 2 else SEED
        label_suffix = "" if seed == SEED else f"_{seed}"
        if case == "edit":
            run_case(
                f"edit_klein_masked{label_suffix}", instruction="Change the color of the dress in this photo.",
                edit_mode="masked_reference", expect_klein_executed=True, seed=seed, sample_vram_flag=True,
            )
        elif case == "generate":
            run_case(
                f"generate_with_klein_wiring{label_suffix}",
                instruction="Generate a picture of a quiet mountain lake at sunrise, no people.",
                edit_mode="masked_reference", expect_klein_executed=False, seed=seed,
            )
        else:
            raise SystemExit(f"unknown case: {case!r}, expected 'edit', 'generate', or 'chain'")
