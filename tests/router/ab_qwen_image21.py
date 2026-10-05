"""
Qwen-Image-2.1 (NVFP4, community quant) smoke test - the smallest useful
test before anything about its native multi-reference editing (up to 16
images via TextEncodeQwenImage21, per live /object_info): does plain
text-to-image generation work at all on this checkpoint/text-encoder/VAE
set, verified via actually submitting to ComfyUI and inspecting the output.

Graph verified against this install's live ComfyUI source and /object_info,
not guessed:
- comfy/supported_models.py's QwenImage21 class: sampling_settings
  shift=0.69 (auto-applied on model load, no manual ModelSamplingAuraFlow
  node needed - unlike this project's existing Qwen Image Edit 2511 graph).
- comfy/sd.py line ~1981: CLIPLoader type="qwen_image" auto-detects between
  the original Qwen-Image (2511) and Qwen-Image-2.1 by inspecting the
  checkpoint's actual TEModel (QWEN3VL_8B -> qwen_image21.te()/
  QwenImage21Tokenizer) - there is no separate "qwen_image21" dropdown
  entry, "qwen_image" is correct for both.
- TextEncodeQwenImage21 (comfy_extras/nodes_qwen.py) outputs
  (positive, negative, latent) in one node - the latent is pre-sized
  (1024x1024 here via `resolution`, no reference images given) so no
  separate EmptyLatentImage node is needed either.
- Sampler settings per the Civitai uploader's own tested starting point
  (model card): Euler, 40 steps, CFG 1, Normal scheduler, denoise=1.0.

UNET is a third-party NVFP4+Q4 community quant (civitai.com/models/2957912,
"Native Test" per the uploader's own description - not an official BFL/
Qwen-team release) - a positive result here is evidence for THIS quant
specifically, not a general Qwen-Image-2.1 capability claim.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

UNET_NAME = r"Qwen Image 2.1\qwenImage21Nvfp4Q4_nvfp4.safetensors"
CLIP_NAME = r"Qwen Image 2.1\qwen3vl_8b_w4a8.safetensors"
VAE_NAME = r"Qwen Image 2.1\qwen_image_2.1_vae_bf16.safetensors"

PROMPT = "A photo of a red bicycle leaning against a brick wall, golden hour lighting, shallow depth of field."


def build(seed: int) -> dict:
    graph = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP_NAME, "type": "qwen_image"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
        "encode": {
            "class_type": "TextEncodeQwenImage21",
            "inputs": {
                "clip": ["clip", 0], "prompt": PROMPT, "negative_prompt": "",
                "resolution": 1024,
            },
        },
        "sample": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["unet", 0], "positive": ["encode", 0], "negative": ["encode", 1],
                "latent_image": ["encode", 2], "seed": seed, "steps": 40, "cfg": 1,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_QwenImage21Test"}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 424242
    assert_queue_empty()
    free()
    graph = build(seed)
    pid = submit(graph)
    print(json.dumps({"event": "submitted", "prompt_id": pid}))
    result = poll_history(pid, timeout_s=600)
    outs = result.get("outputs", {})
    summary = {
        "prompt_id": pid,
        "status_completed": result.get("status", {}).get("completed"),
        "filenames": [i["filename"] for i in outs.get("save", {}).get("images", [])],
    }
    print(json.dumps(summary, indent=2))
