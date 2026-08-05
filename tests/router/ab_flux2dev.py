"""
Flux.2 Dev capability test for case 3's locality problem (Codex-designed,
thread 019fd14f-0515-7a91-958a-ce162f468ce2). All non-masking levers on the
Qwen Image Edit 2511 path are exhausted (RESULTS_ref_weight.md); user asked
to test Flux.2 Dev (not Klein - user's explicit judgment that Klein "isn't
capable enough") as a different reference-aware model branch, before
considering masking.

Graph shape follows the existing installed user workflow
(G:\\ComfyUI-Easy-Install\\ComfyUI\\user\\default\\workflows\\Flux.2 Dev\\
TooReal Studio - Flux2 Dev NVFP4 img2img.json), extended from single-image
to case 3's two-image (source + color-swatch reference) shape via
ReferenceLatent chaining (comfy_extras/nodes_edit_model.py's generic
multi-reference mechanism - "chain multiple to set multiple reference
images"), NOT ported from Qwen's cfg/steps/sampler:

    positive text -> ReferenceLatent(source) -> ReferenceLatent(swatch)
    negative zeroed text -> ReferenceLatent(source)   [swatch NOT on negative]

Output samples from an EMPTY Flux2 latent at the source's scaled size, not
from the source latent directly - source/swatch are edit/reference
conditioning only, matching the working example workflow's own pattern.

This is a branch-capability smoke test, not a router-ready implementation -
per Codex, multi-reference ReferenceLatent chaining is plausible from the
node's docstring but unproven until this test (the example workflow was
single-reference only).
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

# Flux-native prompt, not Qwen's known-bad "background" wording - testing
# Flux.2 Dev capability, not rescuing Qwen's prompt pathology (Codex).
PROMPT = (
    "Change only the woman's black leather dress to match the blue material shown in the second "
    "reference image. Keep her face, hair, skin, pose, bench, buildings, pavement, sky, lighting, "
    "camera framing, and all background details unchanged."
)


def build(seed: int) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "src_scale": {
            "class_type": "ImageScaleToTotalPixels",
            "inputs": {"image": ["src", 0], "upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 16},
        },
        "get_size": {"class_type": "GetImageSize", "inputs": {"image": ["src_scale", 0]}},

        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Flux.2 Dev\\flux2-dev-nvfp4-mixed.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Flux.2 Dev\\mistral_3_small_flux2_fp4_mixed.safetensors", "type": "flux2"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Flux.2\\flux2-vae.safetensors"}},

        "src_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["src_scale", 0], "vae": ["vae", 0]}},
        "ref2_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["ref2", 0], "vae": ["vae", 0]}},

        "pos_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": PROMPT}},
        "pos_ref1": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_text", 0], "latent": ["src_latent", 0]}},
        "pos_ref2": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos_ref1", 0], "latent": ["ref2_latent", 0]}},

        "neg_base": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos_text", 0]}},
        "neg_ref1": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["neg_base", 0], "latent": ["src_latent", 0]}},

        "empty_latent": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": ["get_size", 0], "height": ["get_size", 1], "batch_size": 1}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "guider": {"class_type": "CFGGuider", "inputs": {"model": ["unet", 0], "positive": ["pos_ref2", 0], "negative": ["neg_ref1", 0], "cfg": 1.2}},
        "scheduler": {"class_type": "Flux2Scheduler", "inputs": {"steps": 28, "width": ["get_size", 0], "height": ["get_size", 1]}},
        "sampler_select": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "dpmpp_sde"}},
        "sample": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler_select", 0], "sigmas": ["scheduler", 0], "latent_image": ["empty_latent", 0]},
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "ImageDirector_ABflux2dev"}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    seed = int(sys.argv[1])
    graph = build(seed)
    with open(f"tests/router/runs/AB_flux2dev_{seed}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "seed": seed, "filenames": filenames}, indent=2))
