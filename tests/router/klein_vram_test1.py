"""
VRAM/timing instrumentation for the FLUX.2 Klein 9B distilled masked-
reference mechanism (tests/router/klein_test1_masked_reference.py's variant
B, distilled profile) - Codex's recommended smallest test before deciding
on build_router_graph.py integration (read-only Codex exec session,
2026-10-04, see PROJECT_RULES.md).

Codex's two concrete points this script addresses:
1. The standalone Klein test graph has mask_preview/mask_save as an extra
   OUTPUT_NODE=True execution root that the router's masked_reference
   wiring deliberately omits (to keep the generate/edit lazy switch
   working - see build_router_graph.py's module docstring). The standalone
   script's own VRAM/scheduling shape might not transfer to the router's
   actual topology. Fix: run variant B twice, once with mask_save present
   (the historical standalone shape) and once without (the router's actual
   node set), via klein_test1_masked_reference.build()'s new
   include_mask_preview parameter.
2. The prior VRAM sampling method (tests/router/masking_test2_current_env.py)
   spawned a fresh nvidia-smi subprocess per sample, which had real gaps up
   to 1.2-1.4s despite requesting 250ms - too coarse for this test. Fix:
   one long-lived `nvidia-smi --loop-ms=100` process (verified continuous,
   ~110ms real spacing) instead of a respawn-per-sample loop; actual
   inter-sample gaps are computed from the real timestamps and reported,
   not assumed from the requested interval.

Both runs start from POST /free (clean cold floor), per Codex's "nach
/free vollständig und ungecached ausführen" - VRAM is not comparable
across runs that reuse cached models, and this project's established RV-test
methodology always measures from a clean floor.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
from klein_test1_masked_reference import build, PROMPT_B, REF_IMAGE_RED  # noqa: E402

SEED = 424242  # matches the original variant B run (RESULTS_klein_test1_masked_reference.md)


def sample_vram(csv_path: Path, stop_event: threading.Event, gaps: list, loop_ms: int = 100):
    # Single long-lived nvidia-smi process in loop mode, not a respawn-per-
    # sample loop - see module docstring point 2. Verified continuous
    # ~110ms real spacing in a manual check before writing this.
    proc = subprocess.Popen(
        ["nvidia-smi", "--query-gpu=timestamp,memory.used,memory.free", "--format=csv,noheader,nounits",
         f"-lms={loop_ms}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
    )
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("t,used_mib,free_mib\n")
        last_t = None
        try:
            for line in proc.stdout:
                if stop_event.is_set():
                    break
                t = time.time()
                parts = [p.strip() for p in line.strip().split(",")]
                if len(parts) != 3:
                    continue  # malformed line (e.g. truncated at process kill) - skip, don't crash the sampler
                _, used, used_free = parts[0], parts[1], parts[2]
                f.write(f"{t:.3f},{used},{used_free}\n")
                f.flush()
                if last_t is not None:
                    gaps.append(t - last_t)
                last_t = t
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def run_condition(label: str, include_mask_preview: bool, out_dir: Path, do_free: bool = True, seed: int = SEED):
    assert_queue_empty()
    if do_free:
        free()  # clean cold floor - see module docstring. do_free=False for
        # back-to-back chain runs (added 2026-10-04): the router will never
        # call /free between real user requests, and this project's own
        # established discipline (build_router_graph.py's docstring,
        # RESULTS_RVchain.md/RESULTS_RVref.md) is that VRAM must be proven
        # safe under that back-to-back-without-/free sequencing, not just
        # from a clean floor - a single /free'd run understates real risk.

    csv_path = out_dir / f"vram_log_kleinvram1_{label}.csv"
    hist_path = out_dir / f"history_kleinvram1_{label}.json"
    graph_path = out_dir / f"graph_kleinvram1_{label}.json"

    gaps: list = []
    stop_event = threading.Event()
    sampler = threading.Thread(target=sample_vram, args=(csv_path, stop_event, gaps), daemon=True)
    sampler.start()
    time.sleep(0.3)  # let the sampler get its first sample before the cold floor is disturbed by submit()

    graph = build(seed, PROMPT_B, REF_IMAGE_RED, profile="distilled", include_mask_preview=include_mask_preview)
    graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    t0 = time.time()
    pid = submit(graph)
    result = poll_history(pid, timeout_s=300)
    t1 = time.time()

    time.sleep(0.3)  # one more sample after completion before stopping, for a clean tail
    stop_event.set()
    sampler.join(timeout=3)

    hist_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Parse the CSV back for the summary (simpler than threading shared state for min/max).
    rows = [line.strip().split(",") for line in csv_path.read_text(encoding="utf-8").splitlines()[1:] if line.strip()]
    free_mib = [int(r[2]) for r in rows if len(r) == 3]
    used_mib = [int(r[1]) for r in rows if len(r) == 3]

    outs = result.get("outputs", {})
    summary = {
        "label": label, "include_mask_preview": include_mask_preview, "prompt_id": pid, "seed": seed,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
        "mask_filenames": [i["filename"] for i in outs.get("mask_save", {}).get("images", [])],
        "vram_samples": len(rows),
        "vram_used_max_mib": max(used_mib) if used_mib else None,
        "vram_free_min_mib": min(free_mib) if free_mib else None,
        # Worst-observed margin, not a proven floor - same caveat as
        # RESULTS_masking_test2_current_env.md: a lower, unsampled trough
        # between two real samples cannot be ruled out. The gap stats below
        # bound how large that blind spot plausibly is.
        "sample_gap_s_min": round(min(gaps), 3) if gaps else None,
        "sample_gap_s_max": round(max(gaps), 3) if gaps else None,
        "sample_gap_s_mean": round(sum(gaps) / len(gaps), 3) if gaps else None,
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    out_dir = Path("tests/router/runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    condition = sys.argv[1]  # "with_mask_save" / "no_mask_save" / "chain_no_mask_save"
    if condition == "chain_no_mask_save":
        # Back-to-back-without-/free chain (added 2026-10-04, user-requested
        # follow-up to the single-run no_mask_save result's 212 MiB margin):
        # only the first run gets a clean /free floor, matching how the
        # router would actually be hit by consecutive real requests.
        # Each run uses a DIFFERENT seed - a same-seed/same-graph repeat was
        # tried first and ComfyUI's own node-level caching turned runs 2+3
        # into near-instant cache hits (0.5s, all 18 nodes incl. the KSampler
        # itself reported cached - see history_kleinvram1_chain_no_mask_save_2
        # .json's execution_cached message), which measured nothing real
        # about back-to-back VRAM behavior. Varying the seed forces genuine
        # re-execution of sample/decode/save each time while still never
        # calling /free between runs.
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        summaries = []
        for i in range(1, n + 1):
            summaries.append(run_condition(f"chain_no_mask_save_{i}", False, out_dir, do_free=(i == 1), seed=SEED + i))
        print(json.dumps({"chain_summary": [
            {"run": s["label"], "vram_free_min_mib": s["vram_free_min_mib"], "vram_used_max_mib": s["vram_used_max_mib"]}
            for s in summaries
        ]}, indent=2))
    elif condition == "cold_sweep":
        # Independent cold-start samples (added 2026-10-04, user-requested
        # follow-up to the single no_mask_save/chain-run-1 results: 212 MiB
        # and 367 MiB, both near the project's ~300 MiB safety floor) - each
        # run calls /free first. Different seed per run is not required for
        # correctness here (unlike the chain test): /free was already
        # confirmed to force genuine re-execution even at an identical seed
        # (the original with_mask_save -> no_mask_save pair both used seed
        # 424242 and both executed for real, ~16-20s each, not a cache hit).
        # Varied anyway for a cleaner independent-sample read.
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        start_at = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        summaries = []
        for i in range(start_at, start_at + n):
            summaries.append(run_condition(f"cold_sweep_{i}", False, out_dir, do_free=True, seed=SEED + 100 + i))
        print(json.dumps({"cold_sweep_summary": [
            {"run": s["label"], "vram_free_min_mib": s["vram_free_min_mib"], "vram_used_max_mib": s["vram_used_max_mib"]}
            for s in summaries
        ]}, indent=2))
    else:
        include_mask_preview = condition == "with_mask_save"
        run_condition(condition, include_mask_preview, out_dir)
