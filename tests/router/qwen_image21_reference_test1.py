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

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

UNET_NAME = r"Qwen Image 2.1\qwenImage21Nvfp4Q4_nvfp4.safetensors"
CLIP_NAME = r"Qwen Image 2.1\qwen3vl_8b_w4a8.safetensors"
VAE_NAME = r"Qwen Image 2.1\qwen_image_2.1_vae_bf16.safetensors"

SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
REF_IMAGE_GREEN = "imgdir_masktest2_ref_green.png"

# No color named, deliberately - same wording family as the Klein/Dev tests'
# proven PROMPT_B, adapted to name the images explicitly (this node has no
# SAM3 mask to localize "the dress" - the model must find it itself).
PROMPT_B = (
    "Change only the woman's dress in the first image to match the second reference image. "
    "Keep her face, pose, and the entire background exactly unchanged."
)
# D reuses the identical wording even with no second image, matching the
# same "dangling reference phrase" ablation design used for Klein's D variant.


def build(seed: int, ref_image: str | None) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": SOURCE_IMAGE}},
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP_NAME, "type": "qwen_image"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
    }
    encode_inputs = {
        "clip": ["clip", 0], "vae": ["vae", 0], "prompt": PROMPT_B, "negative_prompt": "",
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


def run_variant(name: str, seed: int, ref_image: str | None):
    assert_queue_empty()
    free()
    graph = build(seed, ref_image)
    with open(f"tests/router/runs/qwen21_reftest1_variant{name}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    print(json.dumps({"event": "submitted", "variant": name, "prompt_id": pid}))
    result = poll_history(pid, timeout_s=300)
    outs = result.get("outputs", {})
    summary = {
        "variant": name, "prompt_id": pid,
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    variant = sys.argv[1]  # "B", "D", "B2"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    variants = {"B": REF_IMAGE_RED, "D": None, "B2": REF_IMAGE_GREEN}
    run_variant(variant, seed, variants[variant])
