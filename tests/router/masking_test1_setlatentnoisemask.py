"""
First hard-masking test for case 3's reference-bleed problem, after the
mechanism-level (attention-only) investigation was exhausted and negative
(RESULTS_sam3_spike_stage3.md). User explicitly approved pursuing masking
("dann masking") once every softer alternative failed.

Codex-agreed design (thread 019fd14f-0515-7a91-958a-ce162f468ce2): unlike
the attention-bias spike (which tried to influence the model's internal
routing and failed), this constrains locality at the SAMPLER/LATENT
level via the standard core node SetLatentNoiseMask (nodes.py:1541, no
custom code) - outside the mask, the original latent gets blended back in
at every denoising step, so global tint cannot occur there regardless of
what the model "wants" to do internally.

Pipeline: SAM3 mask ("the woman's dress") on the source image -> resized
to the source latent's spatial size -> SetLatentNoiseMask -> normal
KSampler with the same known-bad prompt/reference/seed used throughout
this session's investigation.

Acceptance (Codex): outside mask preserved (no blue tint), dress changes
toward reference, no catastrophic seam/body damage. First run proves the
mechanism, not polished - mask blur/grow tuning comes after if needed.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_WITH_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)

PROMPT_MASKED_SIMPLE = (
    "Change only the masked dress to match the blue color and material of Reference Image #2. "
    "Keep everything outside the mask unchanged."
)

SAM3_PROMPT = "the woman's dress"


def build(seed: int, use_mask: bool, prompt_text: str = PROMPT_WITH_BACKGROUND) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "prompt_literal": {"class_type": "PrimitiveString", "inputs": {"value": prompt_text}},
        "neg_str": {"class_type": "StringSubstring", "inputs": {"string": ["prompt_literal", 0], "start": 0, "end": 0}},

        "edit_unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen-image-edit-2511-Q4_K_M.gguf"}},
        "edit_clip": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Qwen2.5-VL-7B-abliterated\\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf", "type": "qwen_image"}},
        "edit_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Qwen Image Edit 2509\\qwen_image_vae.safetensors"}},
        "edit_scale": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["src", 0]}},
        "edit_model": {"class_type": "CFGNorm", "inputs": {"model": ["edit_unet", 0], "strength": 1.0}},
        "edit_model_s": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["edit_model", 0], "shift": 3}},
        "edit_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["edit_scale", 0], "vae": ["edit_vae", 0]}},
        "edit_cond_pos": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["edit_clip", 0], "vae": ["edit_vae", 0],
                "image1": ["edit_scale", 0], "image2": ["ref2", 0],
                "prompt": ["prompt_literal", 0],
            },
        },
        "edit_cond_neg": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["edit_clip", 0], "vae": ["edit_vae", 0],
                "image1": ["edit_scale", 0], "image2": ["ref2", 0],
                "prompt": ["neg_str", 0],
            },
        },
        "edit_image": {"class_type": "VAEDecode", "inputs": {"samples": ["edit_sample", 0], "vae": ["edit_vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_MaskTest1"}},
    }

    latent_for_sampler = ["edit_latent", 0]
    if use_mask:
        graph["sam3_load"] = {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}}
        graph["sam3_seg"] = {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["edit_scale", 0], "prompt": SAM3_PROMPT,
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        }
        graph["mask_preview"] = {"class_type": "SaveImage", "inputs": {"images": ["sam3_seg", 1], "filename_prefix": "ImageDirector_MaskTest1_maskpreview"}}
        graph["noise_mask"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["edit_latent", 0], "mask": ["sam3_seg", 0]}}
        latent_for_sampler = ["noise_mask", 0]

    graph["edit_sample"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["edit_model_s", 0], "positive": ["edit_cond_pos", 0], "negative": ["edit_cond_neg", 0],
            "latent_image": latent_for_sampler, "seed": seed, "steps": 8, "cfg": 2.5,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
        },
    }
    return {"prompt": graph}


if __name__ == "__main__":
    variant = sys.argv[1]  # "baseline", "masked", or "masked_simpleprompt"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    prompt_text = PROMPT_MASKED_SIMPLE if variant == "masked_simpleprompt" else PROMPT_WITH_BACKGROUND
    graph = build(seed, use_mask=(variant != "baseline"), prompt_text=prompt_text)
    with open(f"tests/router/runs/AB_masktest1_{variant}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid, timeout_s=300)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    mask_out = outs.get("mask_preview", {})
    mask_filenames = [i["filename"] for i in mask_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "seed": seed, "filenames": filenames, "mask_filenames": mask_filenames}, indent=2))
