"""
Render-level repeat-seed check for content-quality cases 1/2 - the part
RESULTS_repeat_seed_cases12.md's analyzer-only pass explicitly left open
("No render-level (KSampler) repeat-seed pass done yet"). Full router
(build_router_graph.build()), real image generation, n=3 per case (smaller
than the n=5 analyzer-only pass - each run is a full UNet/VAE load +
KSampler pass, not a cheap analyzer-only call).

Same instructions as RESULTS_content_quality.md/RESULTS_repeat_seed_cases12.md.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from build_router_graph import build
from comfy_submit import submit, poll_history

CASES = {
    "case1": "Remove the beer bottle standing on top of the trash can. Keep the woman, her clothing, and everything else in the scene unchanged.",
    "case2": "Restyle the entire photo as a vintage 1970s film photograph with warm faded colors and visible film grain.",
}

if __name__ == "__main__":
    case = sys.argv[1]
    seed = int(sys.argv[2])
    analyzer_seed = int(sys.argv[3])
    graph = build(CASES[case], seed, analyzer_seed, refs=[])
    # Router loads the default fixture image; point it at the real photo
    # used throughout this session's content-quality testing.
    graph["prompt"]["src"]["inputs"]["image"] = "IMG_7148.jpg"
    with open(f"tests/router/runs/RSR_{case}_{seed}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"case": case, "prompt_id": pid, "seed": seed, "analyzer_seed": analyzer_seed, "filenames": filenames}, indent=2))
