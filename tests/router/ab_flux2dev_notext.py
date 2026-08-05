"""
Decisive follow-up (Codex-designed, thread 019fd14f-0515-7a91-958a-ce162f468ce2):
does Flux.2 Dev's image reference actually carry color/material information
the text prompt CANNOT express, or did ab_flux2dev.py's success come from
the prompt's own "blue material" wording (confirmed via
ab_flux2dev_ablation.py - source-only ablation also turned the dress blue)?

Prompt below has NO color/material descriptor at all - only "match the
appearance shown in the second reference image." If Flux.2 Dev can still
recolor the dress toward the swatch's blue using ONLY the image, while the
source-only ablation (same prompt, no swatch) does NOT turn it blue, that
proves genuine image-reference transfer - the actual capability this
project's reference-image workflow (garment_reference/
material_style_reference roles) depends on.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_NO_COLOR_NAME = (
    "Change only the woman's black leather dress to match the appearance shown in the second "
    "reference image. Keep her face, hair, skin, pose, bench, buildings, pavement, sky, lighting, "
    "camera framing, and all background details unchanged."
)


def build(seed: int, with_swatch: bool) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "src_scale": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["src", 0], "upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 16}},
        "get_size": {"class_type": "GetImageSize", "inputs": {"image": ["src_scale", 0]}},
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Flux.2 Dev\\flux2-dev-nvfp4-mixed.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Flux.2 Dev\\mistral_3_small_flux2_fp4_mixed.safetensors", "type": "flux2"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Flux.2\\flux2-vae.safetensors"}},
        "src_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["src_scale", 0], "vae": ["vae", 0]}},
        "pos_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": PROMPT_NO_COLOR_NAME}},
        "pos_ref1": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_text", 0], "latent": ["src_latent", 0]}},
        "neg_base": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos_text", 0]}},
        "neg_ref1": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["neg_base", 0], "latent": ["src_latent", 0]}},
        "empty_latent": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ["get_size", 0], "height": ["get_size", 1], "batch_size": 1}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "scheduler": {"class_type": "Flux2Scheduler", "inputs": {"steps": 28, "width": ["get_size", 0], "height": ["get_size", 1]}},
        "sampler_select": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "dpmpp_sde"}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_ABflux2dev_notext"}},
    }

    positive_cond = ["pos_ref1", 0]
    if with_swatch:
        graph["ref2"] = {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}}
        graph["ref2_latent"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["ref2", 0], "vae": ["vae", 0]}}
        graph["pos_ref2"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_ref1", 0], "latent": ["ref2_latent", 0]}}
        positive_cond = ["pos_ref2", 0]

    graph["guider"] = {"class_type": "CFGGuider", "inputs": {"model": ["unet", 0], "positive": positive_cond, "negative": ["neg_ref1", 0], "cfg": 1.2}}
    graph["sample"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {"noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler_select", 0], "sigmas": ["scheduler", 0], "latent_image": ["empty_latent", 0]},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    variant = sys.argv[1]  # "swatch" or "noswatch"
    seed = int(sys.argv[2])
    graph = build(seed, with_swatch=(variant == "swatch"))
    with open(f"tests/router/runs/AB_flux2dev_notext_{variant}_{seed}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid, timeout_s=480)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "seed": seed, "filenames": filenames}, indent=2))
