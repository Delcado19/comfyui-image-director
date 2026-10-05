"""
Qwen-Image-2.1 (NVFP4 community quant) native multi-reference editing test -
does this model transfer a reference image's color onto a named region
WITHOUT the color being named in text, using its own native TextEncodeQwenImage21
node (no SAM3 masking, no hand-built ReferenceLatent chain)?

Mechanism, read directly from comfy_extras/nodes_qwen.py's
TextEncodeQwenImage21.execute() (not guessed): each non-None entry in
`images` is (a) resized and fed to the Qwen3VL-8B text encoder's vision
tower as part of prompt tokenization (clip.tokenize(images=...)) - genuine
multimodal image understanding, not just a text-only encoder - and (b), if
`vae` is given, separately VAE-encoded and appended to both positive and
negative conditioning's `reference_latents` list via
node_helpers.conditioning_set_values(..., append=True) - the SAME
conditioning key ReferenceLatent sets for Klein/Dev. The output latent is
EMPTY (torch.zeros, sized to the first image), not source-latent-plus-mask -
sampling is full regeneration from noise, guided only by conditioning, same
class of mechanism as ab_flux2dev.py's closed-out (negative-result) empty-
latent approach, NOT Klein/Dev's SetLatentNoiseMask anchoring. Locality is
therefore not structurally guaranteed here either - this is a genuinely
open question for this specific model/mechanism, not assumed from Dev's
unrelated closed result (different text encoder entirely: Qwen3VL is a real
VLM seeing the reference pixels directly, vs. Dev's text-only Mistral).

Causal matrix (same fixtures/prompts as klein_test1_masked_reference.py and
flux2dev_masking_test1.py, for direct comparability):
    B  - no color named + red reference (image_2)  - the real causal question
    D  - no color named + NO reference (image_1 only) - ablation
    B2 - no color named + green reference (image_2) - causal color-swap control
(Variant A - color named - skipped: the "does text-driven editing work at
all" question is already well-established for Qwen-family models in this
project; the open question here is specifically image-based transfer.)

image_1 = source (its size also becomes the sampled latent's size - this
node samples from scratch, not from the source's own latent); image_2 =
reference, when present.

Wiring note (found the hard way, see RESULTS_qwen_image21_reference_test1.md):
`images` is a COMFY_AUTOGROW_V3 DYNAMIC input (comfy_api/latest/_io.py) -
it does NOT accept a nested `"images": {"image_1": [...], ...}` dict in the
API graph JSON, even though that is what the /object_info schema's nesting
visually suggests and ComfyUI's validation accepts it silently with no
node_errors. It expands into flattened top-level inputs named
"{id}.{name}" (dot-joined, via finalize_prefix) - use
"images.image_1"/"images.image_2" as direct top-level keys in the node's
`inputs` dict instead. The first (wrong) attempt ran without any error but
produced pixel-identical output whether or not a reference image was
attached (confirmed via /history - not a cache hit, a genuine fresh
execution that silently treated the image as absent).
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\router")
from klein_vram_test1 import sample_vram  # noqa: E402 - reuse the same loop-mode sampler

OUT_DIR = Path("tests/router/runs")

UNET_NAME = r"Qwen Image 2.1\qwenImage21Nvfp4Q4_nvfp4.safetensors"
CLIP_NAME = r"Qwen Image 2.1\qwen3vl_8b_w4a8.safetensors"
VAE_NAME = r"Qwen Image 2.1\qwen_image_2.1_vae_bf16.safetensors"

SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
REF_IMAGE_GREEN = "imgdir_masktest2_ref_green.png"
# Real leather photo (user-supplied, not synthetic) - already used and
# proven for the Flux.2 Dev material test (RESULTS_flux2dev_masking_test1.md).
# Unlike that graph, no manual reference-scaling guard is needed here:
# TextEncodeQwenImage21 already resizes every image (including references)
# to ~`resolution`x`resolution` internally (per its own tooltip), so the
# 3000x2000 source photo cannot blow up VRAM the way it did for the
# hand-built Dev graph.
REF_IMAGE_LEATHER = "imgdir_masktest2_ref_leather.png"
# Literal case-3 recreation (added 2026-10-05): the original fixtures
# (IMG_7148.jpg - black leather dress, person, outdoor scene - and
# imgdir_test_ref2.png - a solid blue swatch) are gone, but the user
# supplied a real replacement photo matching the same shape: a person
# wearing a black latex/leather-look garment outdoors with a rich
# background (sea, railing, mountains, flowers) - the specific thing
# needed to actually observe "does editing the dress bleed onto the
# background", which a garment-only product shot could not test.
SOURCE_IMAGE_BLACKDRESS = "imgdir_casetest3_source_blackdress_cannes.png"
REF_IMAGE_BLUE = "imgdir_masktest2_ref_blue.png"

# No color named, deliberately - same wording family as the Klein/Dev tests'
# proven PROMPT_B, adapted to name the images explicitly (this node has no
# SAM3 mask to localize "the dress" - the model must find it itself).
PROMPT_B = (
    "Change only the woman's dress in the first image to match the second reference image. "
    "Keep her face, pose, and the entire background exactly unchanged."
)
# D reuses the identical wording even with no second image, matching the
# same "dangling reference phrase" ablation design used for Klein's D variant.

# Variant H (added 2026-10-05): the original case-3 fixtures (IMG_7148.jpg,
# imgdir_test_ref2.png - black leather dress + blue swatch, the scenario
# Klein was judged "not capable enough" for, see PROJECT_RULES.md) were
# deleted during the project's environment-drift pause and are not
# recoverable (PROJECT_RULES.md's 2026-10-03 migration log). This instead
# reuses the EXACT historically-harmful prompt PATTERN, confirmed via a
# dedicated A/B isolation test (RESULTS_ab_background_word.md) to cause
# Qwen Image Edit 2511's global-tint bleeding failure: an origin-color
# anchor ("needs to be changed") plus the word "background" describing the
# reference swatch itself ("which appears as a solid X background") -
# adapted to this project's current blue-dress fixture/red reference
# instead of the lost black-dress/blue-swatch originals. If Qwen-Image-2.1
# is robust to the exact wording pattern that broke Qwen 2511, that is
# meaningful evidence (not proof of general robustness - a different
# fixture is still untested).
PROMPT_H = (
    "The woman is wearing a blue dress that needs to be changed to match the color from Reference Image #2, "
    "which appears as a solid red background. The rest should remain unchanged."
)

# Variant C3 (added 2026-10-05): same harmful wording pattern as H, but on
# the literal case-3 shape instead of the adapted blue/red fixture - a real
# black-garment source photo + a blue reference swatch, matching the
# original lost fixtures' colors exactly (IMG_7148.jpg was black leather,
# imgdir_test_ref2.png was blue).
PROMPT_C3 = (
    "The woman is wearing a black dress that needs to be changed to match the color from Reference Image #2, "
    "which appears as a solid blue background. The rest should remain unchanged."
)


def build(seed: int, ref_image: str | None, prompt_text: str = PROMPT_B, source_image: str = SOURCE_IMAGE) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": source_image}},
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP_NAME, "type": "qwen_image"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
    }
    encode_inputs = {
        "clip": ["clip", 0], "vae": ["vae", 0], "prompt": prompt_text, "negative_prompt": "",
        "resolution": 1024, "images.image_1": ["src", 0],
    }
    if ref_image is not None:
        graph["ref"] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}
        encode_inputs["images.image_2"] = ["ref", 0]

    graph["encode"] = {"class_type": "TextEncodeQwenImage21", "inputs": encode_inputs}
    graph["sample"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["unet", 0], "positive": ["encode", 0], "negative": ["encode", 1],
            "latent_image": ["encode", 2], "seed": seed, "steps": 40, "cfg": 1,
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
        },
    }
    graph["decode"] = {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}}
    graph["save"] = {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_QwenImage21RefTest1"}}
    return {"prompt": graph}


def run_variant(name: str, seed: int, ref_image: str | None, sample_vram_flag: bool = False, prompt_text: str = PROMPT_B, source_image: str = SOURCE_IMAGE):
    assert_queue_empty()
    free()
    graph = build(seed, ref_image, prompt_text, source_image)
    with open(f"tests/router/runs/qwen21_reftest1_variant{name}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    gaps: list = []
    stop_event = threading.Event()
    sampler = None
    csv_path = OUT_DIR / f"vram_log_qwen21reftest1_{name}.csv"
    if sample_vram_flag:
        sampler = threading.Thread(target=sample_vram, args=(csv_path, stop_event, gaps), daemon=True)
        sampler.start()
        time.sleep(0.3)

    t0 = time.time()
    pid = submit(graph)
    print(json.dumps({"event": "submitted", "variant": name, "prompt_id": pid}))
    result = poll_history(pid, timeout_s=300)
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

    outs = result.get("outputs", {})
    summary = {
        "variant": name, "prompt_id": pid,
        "wall_time_s": round(t1 - t0, 1),
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
        "vram_free_min_mib": vram_free_min_mib,
        "vram_used_max_mib": vram_used_max_mib,
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    variant = sys.argv[1]  # "B", "D", "B2", "M", "H", "C3", "D3"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    # D3 (added 2026-10-05): D's ablation companion on the C3/black-dress
    # fixture - needed as the numeric-locality baseline for
    # qwen21_integration_test2.py's c3fixture case (the router itself
    # cannot build a no-reference call under edit_mode="native_reference",
    # its own contract requires exactly 1 reference image by design).
    variants = {"B": REF_IMAGE_RED, "D": None, "B2": REF_IMAGE_GREEN, "M": REF_IMAGE_LEATHER, "H": REF_IMAGE_RED, "C3": REF_IMAGE_BLUE, "D3": None}
    prompt_text = PROMPT_H if variant == "H" else PROMPT_C3 if variant == "C3" else PROMPT_B
    source_image = SOURCE_IMAGE_BLACKDRESS if variant in ("C3", "D3") else SOURCE_IMAGE
    sample_vram_flag = "--vram" in sys.argv
    run_variant(variant, seed, variants[variant], sample_vram_flag=sample_vram_flag, prompt_text=prompt_text, source_image=source_image)
