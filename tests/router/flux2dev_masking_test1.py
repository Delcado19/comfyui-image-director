"""
Flux.2 Dev + masking (joint Claude-Codex decision, 2026-10-04, Codex exec
thread ba7x2msvh - read-only review of ab_flux2dev.py, RESULTS_flux2dev_
capability.md, PROJECT_RULES.md, and klein_test1_masked_reference.py).

ab_flux2dev.py's validated graph samples from an EMPTY Flux2 latent;
RESULTS_flux2dev_capability.md conclusively found that graph does NOT
transfer reference color/material when the text doesn't name it. This is a
genuinely different mechanism, not a retread: VAEEncode(source) +
SetLatentNoiseMask feeds the SOURCE's own latent into the sampler, with
Dev's installed SamplerCustomAdvanced/CFGGuider/Flux2Scheduler chain kept
exactly as ab_flux2dev.py validated it (cfg=1.2, 28 steps, dpmpp_sde) - no
Klein-style 4-step settings ported over.

Per Codex's correction to Claude's initial framing: Flux2Scheduler starts
its sigma schedule at 1 everywhere, including inside the mask - there is no
"only resolve an already-correct region" inside the mask, full denoise-
from-noise happens there too. KSamplerX0Inpaint-style reinsertion only
anchors the OUTSIDE-mask region to the source latent during sampling. The
actual new mechanism under test here is "held spatial source context
during local synthesis" feeding a positive ReferenceLatent chain, not a
claim that masking alone changes how much noise is removed.

GGUF note: the only installed Flux.2 Dev UNet is flux2_dev-Q4_K_M.gguf.
RESULTS_flux2dev_capability.md's historical validation ran on an NVFP4
UNet - a DIFFERENT quantization format - so that closed investigation's
result does not transfer by precedent; this GGUF checkpoint has not itself
been validated for the empty-latent mechanism either. User explicitly
approved proceeding with the installed GGUF Q4_K_M for this feasibility
test (2026-10-04) rather than downloading an alternative.

Causal matrix (Codex's design, Klein's fixtures/prompts reused for direct
comparability - same blue-dress source, same red/green reference swatches):

    A  - color named ("red") + red reference  - does masked edit work at all?
    B  - no color named       + red reference  - image-based color transfer
    D  - no color named       + no reference   - reference ablation
    B2 - no color named       + green reference - causal color-swap control
    D2 - fallback only if D drifts (same dangling-reference risk Klein's
         Base checkpoint showed) - explicit "keep unchanged" prompt instead
         of reusing B's wording with nothing to resolve it against.

Run order per Codex: shared seed, A -> B -> B2 -> D. Stop if A fails
(reference question isn't evaluable yet). If B shows no change, still run D
before B2 (isolates "no reference effect" from "no causal color-follow").

"baseline" mode (not part of the causal matrix): VAEEncode -> VAEDecode
round-trip with no sampling at all, source image unscaled by the test's
mask/sampling path. Needed per Codex's validation note - pixel differences
from a masked edit must be measured against pure VAE reconstruction loss,
not against the original file, since VAE encode/decode is not lossless.

Deliberately NOT changed from the first attempt (separate, untested
variables - do not introduce simultaneously per Codex):
- No partial-denoise / sigma-schedule adjustment inside the mask.
- No VLM captioning, no post-hoc color correction.
- No image scaling applied to the reference image (matches ab_flux2dev.py
  and klein_test1_masked_reference.py precedent - source is the only image
  scaled, to keep the latent/mask/scheduler width-height consistent).
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE_RED = "imgdir_masktest2_ref_red.png"
REF_IMAGE_GREEN = "imgdir_masktest2_ref_green.png"
SAM3_PROMPT = "the woman's dress"

UNET_NAME = r"Flux.2 Dev\flux2_dev-Q4_K_M.gguf"
CLIP_NAME = r"Flux.2 Dev\mistral_3_small_flux2_nvfp4_mixed.safetensors"
VAE_NAME = r"Flux.2\flux2-vae.safetensors"

# Reused verbatim from klein_test1_masked_reference.py's already-proven
# wording, for direct comparability across models on the same fixtures.
PROMPT_A = (
    "Change only the masked dress to match the red color and material of the second reference image. "
    "Keep everything outside the mask unchanged."
)
PROMPT_B = (
    "Change only the masked dress to match the second reference image. "
    "Keep everything outside the mask unchanged."
)
PROMPT_D2 = "Keep the masked dress unchanged. Do not alter its color or material."


def build(seed: int, prompt_text: str, ref_image: str | None, include_mask_preview: bool = True) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": SOURCE_IMAGE}},
        "src_scale": {
            "class_type": "ImageScaleToTotalPixels",
            "inputs": {"image": ["src", 0], "upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 16},
        },
        "get_size": {"class_type": "GetImageSize", "inputs": {"image": ["src_scale", 0]}},

        "unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET_NAME}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP_NAME, "type": "flux2"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},

        "src_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["src_scale", 0], "vae": ["vae", 0]}},

        "sam3_load": {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}},
        "sam3_seg": {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["src_scale", 0], "prompt": SAM3_PROMPT,
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        },
        "noise_mask": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["src_latent", 0], "mask": ["sam3_seg", 0]}},

        "pos_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt_text}},
        "pos_ref_src": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_text", 0], "latent": ["src_latent", 0]}},

        "neg_base": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos_text", 0]}},
        "neg_ref_src": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["neg_base", 0], "latent": ["src_latent", 0]}},

        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "scheduler": {"class_type": "Flux2Scheduler", "inputs": {"steps": 28, "width": ["get_size", 0], "height": ["get_size", 1]}},
        "sampler_select": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "dpmpp_sde"}},

        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_Flux2DevMaskTest1"}},
    }
    if include_mask_preview:
        graph["mask_preview"] = {"class_type": "MaskToImage", "inputs": {"mask": ["sam3_seg", 0]}}
        graph["mask_save"] = {"class_type": "SaveImage", "inputs": {"images": ["mask_preview", 0], "filename_prefix": "ImageDirector_Flux2DevMaskTest1_mask"}}

    if ref_image is not None:
        graph["ref"] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}
        graph["ref_latent"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["ref", 0], "vae": ["vae", 0]}}
        graph["pos_ref_ref"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_ref_src", 0], "latent": ["ref_latent", 0]}}
        positive_input = ["pos_ref_ref", 0]
    else:
        positive_input = ["pos_ref_src", 0]

    graph["guider"] = {"class_type": "CFGGuider", "inputs": {"model": ["unet", 0], "positive": positive_input, "negative": ["neg_ref_src", 0], "cfg": 1.2}}
    graph["sample"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {"noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler_select", 0], "sigmas": ["scheduler", 0], "latent_image": ["noise_mask", 0]},
    }
    return {"prompt": graph}


def build_baseline() -> dict:
    """Pure VAEEncode -> VAEDecode round-trip, no sampling. Establishes the
    VAE reconstruction-loss floor outside the mask, per Codex's validation
    note - locality must be measured against this, not the original file.
    """
    return {"prompt": {
        "src": {"class_type": "LoadImage", "inputs": {"image": SOURCE_IMAGE}},
        "src_scale": {
            "class_type": "ImageScaleToTotalPixels",
            "inputs": {"image": ["src", 0], "upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 16},
        },
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
        "src_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["src_scale", 0], "vae": ["vae", 0]}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["src_latent", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_Flux2DevMaskTest1_vaebaseline"}},
    }}


def run_variant(name: str, seed: int, prompt_text: str, ref_image: str | None):
    assert_queue_empty()
    free()
    graph = build(seed, prompt_text, ref_image)
    with open(f"tests/router/runs/flux2dev_masktest1_variant{name}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    print(json.dumps({"event": "submitted", "variant": name, "prompt_id": pid}))
    # GGUF quantization overhead and 28 steps are both unproven for runtime
    # on this exact checkpoint - the NVFP4 build took >480s in the earlier
    # closed investigation; allow generous headroom rather than guess.
    result = poll_history(pid, timeout_s=1200)
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


def run_baseline():
    assert_queue_empty()
    free()
    graph = build_baseline()
    pid = submit(graph)
    result = poll_history(pid, timeout_s=120)
    outs = result.get("outputs", {})
    summary = {
        "variant": "baseline", "prompt_id": pid,
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    variant = sys.argv[1]  # "A", "B", "D", "D2", "B2", "baseline"
    if variant == "baseline":
        run_baseline()
    else:
        seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
        variants = {
            "A": (PROMPT_A, REF_IMAGE_RED),
            "B": (PROMPT_B, REF_IMAGE_RED),
            "D": (PROMPT_B, None),
            "D2": (PROMPT_D2, None),
            "B2": (PROMPT_B, REF_IMAGE_GREEN),
        }
        prompt_text, ref_image = variants[variant]
        run_variant(variant, seed, prompt_text, ref_image)
