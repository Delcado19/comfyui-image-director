"""
Stage 2 of the SAM3-attention-hint spike: verify QwenBlockAttnReimplProbe's
hand-copied Attention.forward reimplementation (no bias yet) reproduces the
unpatched baseline exactly. Same graph/prompt/seed as
sam3_spike_stage1_probe.py, "baseline" = no probe node at all, an int =
block_index to patch with the reimplementation. Compare the two saved PNGs
byte-for-byte - if they differ, the reimplementation has a bug and Stage 3
(adding the SAM3 bias) must not proceed on top of it.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_WITH_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)


def build(block_index: int | None, seed: int) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "prompt_literal": {"class_type": "PrimitiveString", "inputs": {"value": PROMPT_WITH_BACKGROUND}},
        "neg_str": {"class_type": "StringSubstring", "inputs": {"string": ["prompt_literal", 0], "start": 0, "end": 0}},

        "edit_unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen_image_edit_2511_fp8.safetensors", "weight_dtype": "default"}},
        "edit_clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Qwen Image Edit 2511\\qwen2.5_vl_7b_huihui_abliterated_fp8.safetensors", "type": "qwen_image"}},
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
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_SAM3Stage2"}},
    }

    model_for_sampler = ["edit_model_s", 0]
    if block_index is not None:
        graph["probe"] = {"class_type": "QwenBlockAttnReimplProbe", "inputs": {"model": ["edit_model_s", 0], "block_index": block_index}}
        model_for_sampler = ["probe", 0]

    graph["edit_sample"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_for_sampler, "positive": ["edit_cond_pos", 0], "negative": ["edit_cond_neg", 0],
            "latent_image": ["edit_latent", 0], "seed": seed, "steps": 8, "cfg": 2.5,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
        },
    }
    return {"prompt": graph}


if __name__ == "__main__":
    variant = sys.argv[1]  # "baseline" or an int block_index
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    block_index = None if variant == "baseline" else int(variant)
    graph = build(block_index, seed)
    with open(f"tests/router/runs/AB_sam3stage2_{variant}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid, timeout_s=300)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "seed": seed, "filenames": filenames}, indent=2))
