"""
Closes the remaining-risks list from RESULTS_router_qwen21_integration.md
for editor="qwen_image21" / edit_mode="native_reference", all through the
actual router (not standalone):

1. n=1 per color -> n=2: adds red/green at a second seed (777777) through
   the router, pairing with test1's existing red/green outputs at seed
   424243.
2. Numeric locality check: the D-ablation baseline images this needs come
   from qwen_image21_reference_test1.py's variant D/D3 (standalone), NOT
   from this router script - build_router_graph.py's own contract asserts
   exactly 1 reference image for edit_mode="native_reference" (by design,
   matching what was actually validated), so a no-reference call cannot be
   built through build() at all. D's generation subgraph (UNET/CLIP/VAE
   paths, prompt text, sampler settings) is identical between the
   standalone script and this router branch either way - the only
   difference is the surrounding analyzer/switch nodes, which do not
   affect D's own pixel output. See qwen21_locality_numeric.py for the
   actual pixel math (no SAM3 mask exists in this branch's own graph
   either, so the mask used for scoring is generated once, standalone, by
   qwen21_mask_gen.py, purely for evaluation, not part of the router path).
3. Material (M, leather) and the C3 fixture (real black-dress photo + blue
   reference) through the router, using the router's actual fixed prompt
   (QWEN21_PROMPT) - NOT the standalone script's PROMPT_C3 harmful-pattern
   text, which the router never sends by design (see build_router_graph.py's
   docstring - the prompt is a fixed, unparameterized template, not
   analyzer- or caller-driven). This therefore tests "does the mechanism
   generalize to a different real photo/color pair through the router's
   own safe prompt", NOT a re-test of the harmful-prompt-pattern robustness
   itself - that remains standalone-only (RESULTS_qwen_image21_reference_test1.md's
   variant H/C3), and this script does not claim otherwise.
4. Back-to-back-without-/free chain: n edits in a row, only the first gets
   a clean /free floor, VRAM sampled per run - mirrors
   klein_integration_test1.py's chain case exactly, including its finding
   that varying only the seed is not enough to force genuine re-execution
   (the encode node has no seed dependency) - alternates the reference
   image (red/green) too.
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
from klein_vram_test1 import sample_vram  # noqa: E402

LOG_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log"
SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
REF_IMAGE_GREEN = "imgdir_masktest2_ref_green.png"
REF_IMAGE_LEATHER = "imgdir_masktest2_ref_leather.png"
# C3 fixture (real photo, see RESULTS_qwen_image21_reference_test1.md's
# variant C3) - black latex dress, person, outdoor scene, user-supplied.
SOURCE_IMAGE_BLACKDRESS = "imgdir_casetest3_source_blackdress_cannes.png"
REF_IMAGE_BLUE = "imgdir_masktest2_ref_blue.png"

SEED1 = 424243  # matches qwen21_integration_test1.py's edit_red/edit_green
SEED2 = 777777  # second-seed cross-check, matches the standalone script's convention
OUT_DIR = Path("tests/router/runs")
QWEN21_LOG_MARKERS = ("qwenImage21Nvfp4Q4", "qwen3vl_8b_w4a8")


def log_tail_count():
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def new_log_lines(start):
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()[start:]


def run_case(label: str, seed: int, ref_image: str | None, source_image: str = SOURCE_IMAGE,
             do_free: bool = True, sample_vram_flag: bool = False, timeout_s: int = 300):
    assert_queue_empty()
    if do_free:
        free()

    kwargs = dict(
        instruction="Change the color of the dress in this photo.", seed=seed, analyzer_seed=seed,
        refs=[ref_image] if ref_image else [], edit_mode="native_reference",
        source_image=source_image, editor="qwen_image21",
    )
    graph = build(**kwargs)["prompt"]
    (OUT_DIR / f"graph_qwen21integration2_{label}.json").write_text(
        json.dumps({"prompt": graph}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    gaps: list = []
    stop_event = threading.Event()
    sampler = None
    if sample_vram_flag:
        csv_path = OUT_DIR / f"vram_log_qwen21integration2_{label}.csv"
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

    (OUT_DIR / f"history_qwen21integration2_{label}.json").write_text(
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
        "label": label, "seed": seed, "ref_image": ref_image, "source_image": source_image,
        "prompt_id": pid, "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": filenames,
        "qwen21_executed": bool(qwen21_log_hits) or qwen21_cached_hit,
        "qwen21_cached": qwen21_cached_hit,
        "error_lines": error_lines,
        "vram_free_min_mib": vram_free_min_mib,
        "vram_used_max_mib": vram_used_max_mib,
    }
    print(json.dumps(summary, indent=2))

    if error_lines:
        raise RuntimeError(f"[ERROR] lines in log during {label}: {error_lines}")
    if not result.get("status", {}).get("completed"):
        raise RuntimeError(f"{label} did not complete")
    return summary


if __name__ == "__main__":
    case = sys.argv[1]  # "seed2" / "material" / "c3fixture" / "chain"

    if case == "seed2":
        summaries = [
            run_case("red_seed2", seed=SEED2, ref_image=REF_IMAGE_RED, sample_vram_flag=True),
            run_case("green_seed2", seed=SEED2, ref_image=REF_IMAGE_GREEN),
        ]
        print(json.dumps({"seed2_summary": [s["filenames"] for s in summaries]}, indent=2))

    elif case == "material":
        run_case("material_m", seed=SEED1, ref_image=REF_IMAGE_LEATHER, sample_vram_flag=True)

    elif case == "c3fixture":
        summaries = [
            run_case("c3fixture_edit", seed=SEED1, ref_image=REF_IMAGE_BLUE, source_image=SOURCE_IMAGE_BLACKDRESS, sample_vram_flag=True),
        ]
        print(json.dumps({"c3fixture_summary": [s["filenames"] for s in summaries]}, indent=2))

    elif case == "chain":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        ref_cycle = [REF_IMAGE_RED, REF_IMAGE_GREEN]
        summaries = []
        for i in range(1, n + 1):
            s = run_case(
                f"chain_edit_{i}", seed=SEED1 + i, ref_image=ref_cycle[(i - 1) % len(ref_cycle)],
                do_free=(i == 1), sample_vram_flag=True,
            )
            summaries.append(s)
        print(json.dumps({"chain_summary": [
            {"run": s["label"], "vram_free_min_mib": s["vram_free_min_mib"], "vram_used_max_mib": s["vram_used_max_mib"]}
            for s in summaries
        ]}, indent=2))

    else:
        raise SystemExit(f"unknown case: {case!r}, expected 'seed2', 'material', 'c3fixture', or 'chain'")
