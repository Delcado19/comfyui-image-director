"""
Ablation for RESULTS_flux2dev_capability.md (Codex-required before final
write-up): does the text prompt alone (no swatch ReferenceLatent) also
turn the dress blue/violet, or is the reference image doing real color
work? Same seed as one passing full-conditioning run (314001), same
prompt, same source image - only the swatch's ReferenceLatent removed.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history
from ab_flux2dev import PROMPT

if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 314001
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "src_scale": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["src", 0], "upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 16}},
        "get_size": {"class_type": "GetImageSize", "inputs": {"image": ["src_scale", 0]}},
        "unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Flux.2 Dev\\flux2_dev-Q4_K_M.gguf"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Flux.2 Dev\\mistral_3_small_flux2_nvfp4_mixed.safetensors", "type": "flux2"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Flux.2\\flux2-vae.safetensors"}},
        "src_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["src_scale", 0], "vae": ["vae", 0]}},
        "pos_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": PROMPT}},
        "pos_ref1": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_text", 0], "latent": ["src_latent", 0]}},
        "neg_base": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos_text", 0]}},
        "neg_ref1": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["neg_base", 0], "latent": ["src_latent", 0]}},
        "empty_latent": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ["get_size", 0], "height": ["get_size", 1], "batch_size": 1}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "guider": {"class_type": "CFGGuider", "inputs": {"model": ["unet", 0], "positive": ["pos_ref1", 0], "negative": ["neg_ref1", 0], "cfg": 1.2}},
        "scheduler": {"class_type": "Flux2Scheduler", "inputs": {"steps": 28, "width": ["get_size", 0], "height": ["get_size", 1]}},
        "sampler_select": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "dpmpp_sde"}},
        "sample": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler_select", 0], "sigmas": ["scheduler", 0], "latent_image": ["empty_latent", 0]},
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_ABflux2dev_ablation"}},
    }
    graph = {"prompt": graph}
    with open(f"tests/router/runs/AB_flux2dev_ablation_{seed}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid, timeout_s=480)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "seed": seed, "filenames": filenames}, indent=2))
