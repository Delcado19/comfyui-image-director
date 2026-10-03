"""
Stage 1 of the SAM3-attention-hint spike (see memory
project-router-state-2026-08-03.md and RESULTS_ref_weight.md for the full
decision trail): verify that custom_nodes/sam3_attn_probe's
QwenBlockPatchLoggerProbe - which registers a patches_replace["dit"]
[("double_block", i)] hook via the official ModelPatcher.set_model_patch_replace
API (no ComfyUI installation changes) - actually fires with the expected
contract on Qwen Image Edit 2511, before building any real attention bias
logic on top of it.

Reuses ab_ref_weight.py's known-good Qwen Image Edit 2511 graph shape,
swapping Flux2KleinRefLatentWeight for the new logging-only probe node.
Not testing image quality here - the KSampler still runs so the block
actually executes, but the interesting output is
custom_nodes/sam3_attn_probe/last_probe_log.json, not the saved image.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_WITH_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)


def build(block_index: int, seed: int) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "prompt_literal": {"class_type": "PrimitiveString", "inputs": {"value": PROMPT_WITH_BACKGROUND}},
        "neg_str": {"class_type": "StringSubstring", "inputs": {"string": ["prompt_literal", 0], "start": 0, "end": 0}},

        "edit_unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen-image-edit-2511-Q4_K_M.gguf"}},
        "edit_clip": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Qwen2.5-VL-7B-abliterated\\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf", "type": "qwen_image"}},
        "edit_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Qwen Image Edit 2509\\qwen_image_vae.safetensors"}},
        "edit_scale": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["src", 0]}},
        "edit_model": {"class_type": "CFGNorm", "inputs": {"model": ["edit_unet", 0], "strength": 1.0}},
        "edit_model_s": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["edit_model", 0], "shift": 3}},
        "probe": {"class_type": "QwenBlockPatchLoggerProbe", "inputs": {"model": ["edit_model_s", 0], "block_index": block_index}},
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
        "edit_sample": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["probe", 0], "positive": ["edit_cond_pos", 0], "negative": ["edit_cond_neg", 0],
                "latent_image": ["edit_latent", 0], "seed": seed, "steps": 8, "cfg": 2.5,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            },
        },
        "edit_image": {"class_type": "VAEDecode", "inputs": {"samples": ["edit_sample", 0], "vae": ["edit_vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_SAM3SpikeStage1"}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    block_index = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    graph = build(block_index, seed)
    with open(f"tests/router/runs/AB_sam3stage1_block{block_index}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid, timeout_s=300)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "block_index": block_index, "seed": seed, "filenames": filenames}, indent=2))
