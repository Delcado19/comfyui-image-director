"""
Stage 3 (first real test of the core hypothesis) of the SAM3-attention-hint
spike. Builds on Stage 2's verified-faithful attn reimplementation
(RESULTS_sam3_spike_stage2.md) by adding a real SAM3-mask-derived
query-key bias via QwenSam3AttnBiasProbe: source-image query tokens
INSIDE the SAM3 "dress" mask get boosted attention toward the reference
image's (image2/ref2) key tokens; tokens outside stay at baseline.

Acceptance (Codex, from the original spike-planning consult): "region/
reference bias in 1-3 Qwen blocks without crashing, and the visual
failure moves in the right direction" - modest bar, not a promised fix.
Compares three variants on the known-bad prompt/seed: baseline (no
patch), stage2-style no-bias reimpl (sanity control), and the real
biased variant, at 1-3 mid/late block indices.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_WITH_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)

SAM3_PROMPT = "the woman's dress"


def build(variant: str, block_indices: list[int], seed: int, inside_bias: float, outside_bias: float) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "prompt_literal": {"class_type": "PrimitiveString", "inputs": {"value": PROMPT_WITH_BACKGROUND}},
        "neg_str": {"class_type": "StringSubstring", "inputs": {"string": ["prompt_literal", 0], "start": 0, "end": 0}},

        "edit_unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen-image-edit-2511-Q4_K_M.gguf"}},
        "edit_clip": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Qwen2.5-VL-7B-abliterated\\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf", "type": "qwen_image"}},
        "edit_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Qwen Image Edit 2509\\qwen_image_vae.safetensors"}},
        "edit_scale": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["src", 0]}},
        "get_size": {"class_type": "GetImageSize", "inputs": {"image": ["edit_scale", 0]}},
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
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": f"ImageDirector_SAM3Stage3_{variant}"}},
    }

    model_for_sampler = ["edit_model_s", 0]

    if variant in ("stage2_control", "biased"):
        graph["sam3_load"] = {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}}
        graph["sam3_seg"] = {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["edit_scale", 0], "prompt": SAM3_PROMPT,
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        }

    prev = model_for_sampler
    for i, block_index in enumerate(block_indices):
        node_name = f"probe_{i}"
        if variant == "baseline":
            break
        elif variant == "stage2_control":
            graph[node_name] = {"class_type": "QwenBlockAttnReimplProbe", "inputs": {"model": prev, "block_index": block_index}}
        elif variant == "biased":
            graph[node_name] = {
                "class_type": "QwenSam3AttnBiasProbe",
                "inputs": {
                    "model": prev, "sam3_mask": ["sam3_seg", 0], "block_index": block_index,
                    "source_width": ["get_size", 0], "source_height": ["get_size", 1],
                    "reference_index": 1, "inside_bias": inside_bias, "outside_bias": outside_bias,
                },
            }
        prev = [node_name, 0]
    model_for_sampler = prev

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
    variant = sys.argv[1]  # "baseline", "stage2_control", or "biased"
    blocks = [int(b) for b in sys.argv[2].split(",")] if len(sys.argv) > 2 else [10]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 424242
    inside_bias = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
    outside_bias = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
    graph = build(variant, blocks, seed, inside_bias, outside_bias)
    tag = f"{variant}_" + "-".join(str(b) for b in blocks)
    with open(f"tests/router/runs/AB_sam3stage3_{tag}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid, timeout_s=300)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "blocks": blocks, "seed": seed, "filenames": filenames}, indent=2))
