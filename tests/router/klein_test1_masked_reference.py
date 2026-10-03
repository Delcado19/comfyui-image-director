"""
Smallest first test (per joint Claude-Codex decision, 2026-10-03, Codex exec
session - read-only review of RESULTS_flux2dev_capability.md,
RESULTS_masking_test2_current_env.md, the VTON sibling project's 6.0.4
workflow, and the current ComfyUI v0.38.0 source): does FLUX.2 Klein 9B
(distilled fp8 community fine-tune) + SAM3 masking + native two-way
ReferenceLatent chaining transfer a reference image's color/material onto a
masked region WITHOUT the color being named in the text prompt?

This is Variant A only (masked, color named, reference present) - a
structural/functional smoke test, not yet the causal ablation. Per Codex's
test design, the actual causal question needs B (same prompt, no color
named) vs D (same as B, reference removed) vs B2 (same as B, different
reference color) - not built here, this script is the first rung: does the
pipeline even work at all on this new model before spending more runs on it.

Graph, by design, mirrors tests/router/masking_test2_current_env.py's
mechanism (SAM3 -> SetLatentNoiseMask) but swaps the Qwen Image Edit
machinery for Klein's: TextEncodeQwenImageEditPlus -> plain CLIPTextEncode +
chained ReferenceLatent (source, then reference) - the same native
conditioning path ab_flux2dev.py already used successfully for Flux.2 Dev,
confirmed by reading comfy/model_base.py's Flux.extra_conds() today: Flux2
(the class both Dev and Klein load as) inherits reference_latents handling
from the Flux base class - not a no-op, contrary to Claude's own initial
(wrong, self-corrected) assumption that Klein routed through the unrelated
"Lens" model class.

Settings per Codex's review, not copied uncritically from any one example:
- 4 steps, cfg=1 (BFL's own model card: distilled variant designed for
  4-step inference at guidance_scale=1.0 - caveat, that recommendation is
  for official BFL weights, this installed checkpoint is a community
  fine-tune ("snofs...V12Fp8"), treated as a starting point, not a
  guarantee). Matches the already-installed FLUX.2 klein 9b I2I v2.2.json
  example workflow's own KSampler settings (steps=4, cfg=1, euler, simple,
  denoise=1).
- denoise=1.0, not the VTON sibling project's 0.72 - per Codex: full
  denoise inside the SAM3 mask (the mask mechanism itself, not partial
  denoise, is what preserves everything outside), 0.72 is a separate,
  untested variable not to adopt without its own test.
- VAE: Flux.2's own (flux2-vae.safetensors), matching this model's
  latent_formats.Flux2 - not the shared Flux.1/Z-Image/HiDream VAE used in
  the unrelated pure-text-to-image Base Basic Workflow example.
- No VLM caption stage, no post-hoc ColorMatchV2 - deliberately excluded
  per Codex ("ohne Caption- oder Farbkorrekturstufe") so a pass/fail here
  isolates the native reference mechanism itself, not a color-correction
  safety net papering over a non-functional transfer.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty  # noqa: E402

SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
REF_IMAGE_GREEN = "imgdir_masktest2_ref_green.png"
SAM3_PROMPT = "the woman's dress"

UNET_NAME = r"Flux.2 klein\9B\snofsSexNudesAndOtherFunStuff_distilledV12Fp8.safetensors"
CLIP_NAME = r"Flux.2 klein 9b\qwen3-8b-heretic_fp8_e4m3fn.safetensors"
VAE_NAME = r"Flux.2\flux2-vae.safetensors"

# Variant A: color named in text (functional smoke test - does the
# mechanism work at all on this model).
PROMPT_A = (
    "Change only the masked dress to match the red color and material of the second reference image. "
    "Keep everything outside the mask unchanged."
)
# Variants B/B2: color NOT named - the actual causal question. B and B2 use
# the identical prompt; only the reference image differs (red vs green).
# Per Codex's review: B vs D isolates "does the reference matter at all",
# B vs B2 isolates "does the result follow WHICH reference was given" - the
# stronger, more direct causal test.
PROMPT_B = (
    "Change only the masked dress to match the second reference image. "
    "Keep everything outside the mask unchanged."
)


def build(seed: int, prompt_text: str, ref_image: str | None) -> dict:
    """ref_image=None builds variant D (no reference image / no ReferenceLatent
    for it at all - tests whether the model does anything systematic to the
    masked region without a reference, vs. B/B2's behavior)."""
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": SOURCE_IMAGE}},

        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP_NAME, "type": "flux2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},

        "src_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["src", 0], "vae": ["vae", 0]}},

        "sam3_load": {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}},
        "sam3_seg": {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["src", 0], "prompt": SAM3_PROMPT,
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        },
        "mask_preview": {"class_type": "MaskToImage", "inputs": {"mask": ["sam3_seg", 0]}},
        "mask_save": {"class_type": "SaveImage", "inputs": {"images": ["mask_preview", 0], "filename_prefix": "ImageDirector_KleinTest1_mask"}},
        "noise_mask": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["src_latent", 0], "mask": ["sam3_seg", 0]}},

        "pos_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt_text}},
        "pos_ref_src": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_text", 0], "latent": ["src_latent", 0]}},

        "neg_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": ""}},
        "neg_ref_src": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["neg_text", 0], "latent": ["src_latent", 0]}},

        "sample": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["unet", 0], "positive": ["pos_ref_src", 0], "negative": ["neg_ref_src", 0],
                "latent_image": ["noise_mask", 0], "seed": seed, "steps": 4, "cfg": 1,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            },
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_KleinTest1"}},
    }

    if ref_image is not None:
        graph["ref"] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}
        graph["ref_latent"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["ref", 0], "vae": ["vae", 0]}}
        graph["pos_ref_ref"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_ref_src", 0], "latent": ["ref_latent", 0]}}
        graph["sample"]["inputs"]["positive"] = ["pos_ref_ref", 0]

    return {"prompt": graph}


def run_variant(name: str, seed: int, prompt_text: str, ref_image: str | None):
    assert_queue_empty()
    graph = build(seed, prompt_text, ref_image)
    with open(f"tests/router/runs/klein_test1_variant{name}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    print(json.dumps({"event": "submitted", "variant": name, "prompt_id": pid}))
    result = poll_history(pid, timeout_s=600)
    outs = result.get("outputs", {})
    summary = {
        "variant": name, "prompt_id": pid,
        "status_completed": result.get("status", {}).get("completed"),
        "execution_cached": next((m[1].get("nodes") for m in result.get("status", {}).get("messages", []) if m[0] == "execution_cached"), None),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
        "mask_filenames": [i["filename"] for i in outs.get("mask_save", {}).get("images", [])],
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    variant = sys.argv[1]  # "A", "B", "D", "B2"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    variants = {
        "A": (PROMPT_A, REF_IMAGE_RED),
        "B": (PROMPT_B, REF_IMAGE_RED),
        "D": (PROMPT_B, None),
        "B2": (PROMPT_B, REF_IMAGE_GREEN),
    }
    prompt_text, ref_image = variants[variant]
    run_variant(variant, seed, prompt_text, ref_image)
