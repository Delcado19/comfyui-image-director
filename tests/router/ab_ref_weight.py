"""
Smoke test for a genuine non-masking, mechanism-level alternative to fix
case 3's reference-bleed (Codex-designed, thread
019fd14f-0515-7a91-958a-ce162f468ce2), after prompt-level mitigations
(guidance clause, negative prompt, deterministic templating, few-shot/
temp=0) were all exhausted (see RESULTS_ab_negative_prompt.md,
RESULTS_analyzer_field_reliability*.md).

Found via targeted source inspection (not assumed): comfy/ldm/qwen_image/
model.py populates transformer_options["reference_image_num_tokens"] and
calls each "attn1_patch" with (q, k, v, extra_options=...) - the exact
hook ComfyUI-Flux2Klein-Enhancer's Flux2KleinRefLatentWeight node uses to
scale a specific reference image's attention k/v by a weight. Despite the
package name, this mechanism is not Flux-specific in Qwen's own code path
- it's the same generic attn1_patch hook. Confirmed reference_index
semantics via comfy_extras/nodes_qwen.py: TextEncodeQwenImageEditPlus
builds reference_latents from [image1, image2, image3] in order, so
index 0 = image1 (source), index 1 = image2 (the actual color reference) -
this is what gets down-weighted here, NOT the source image.

Uses the confirmed-bad positive prompt (RESULTS_ab_background_word.md's
"with background" wording, reproduces the whole-image tint) - rescue is
the question, per Codex. Sweep: baseline (no patch), weight 0.7, 0.5, 0.2
on reference_index=1 (image2). Same seed/images throughout.

Acceptance (Codex): scene bleed shrinks while the dress still recolors.
Fail if both scene and dress lose reference influence, or scene still
tints regardless of weight.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_WITH_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)


def build(weight: float | None, seed: int) -> dict:
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
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_ABrefweight"}},
    }

    model_for_sampler = ["edit_model_s", 0]
    if weight is not None:
        graph["ref_weight"] = {
            "class_type": "Flux2KleinRefLatentWeight",
            "inputs": {"model": ["edit_model_s", 0], "reference_index": 1, "weight": weight},
        }
        model_for_sampler = ["ref_weight", 0]

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
    variant = sys.argv[1]  # "baseline" or a float weight like "0.7"
    seed = int(sys.argv[2])
    weight = None if variant == "baseline" else float(variant)
    graph = build(weight, seed)
    with open(f"tests/router/runs/AB_refweight_{variant}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "seed": seed, "filenames": filenames}, indent=2))
