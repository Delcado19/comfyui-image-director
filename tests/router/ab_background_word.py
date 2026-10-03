"""
Isolated A/B test for the "background"-word hypothesis flagged in
RESULTS_content_quality.md's case-3 update as "not proven, not isolated in
an A/B test": did the analyzer describing the blue reference swatch as "a
solid blue background" (vs. just "a solid blue") cause the whole-image tint
failure, or was that only correlated?

The analyzer is non-deterministic (can't force two samples to differ by
exactly one word), so this bypasses it entirely for this one test. Reuses
the exact same edit-branch nodes from build_router_graph.py, but replaces
edit_prompt_str's source (normally GetTextFromJson on the analyzer's output)
with a literal PrimitiveString, per Codex's guidance (thread
019fcb5f-8503-7641-85a0-f7a74b1b7659) - already used the same way in
lazy_switch_probe.py, no invented node. Negative prompt still runs through
StringSubstring(literal, 0, 0) to preserve the same empty-negative
dependency shape the router itself uses.

Same seed, same source image (IMG_7148.jpg), same reference image
(imgdir_test_ref2.png), same edit-branch params both runs - only the prompt
text's "background" clause differs, matching the two real analyzer samples'
wording as closely as possible.

Per Codex: this proves "this exact prompt wording variant affects output",
not that the word "background" alone universally causes the failure -
changing one word necessarily changes surrounding tokenization/context too.
Still the right evidence for this specific hypothesis.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

PROMPT_WITH_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)
PROMPT_WITHOUT_BACKGROUND = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue. The rest should remain unchanged."
)


def build(prompt_text: str, seed: int) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "prompt_literal": {"class_type": "PrimitiveString", "inputs": {"value": prompt_text}},
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
        "edit_sample": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["edit_model_s", 0], "positive": ["edit_cond_pos", 0], "negative": ["edit_cond_neg", 0],
                "latent_image": ["edit_latent", 0], "seed": seed, "steps": 8, "cfg": 2.5,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            },
        },
        "edit_image": {"class_type": "VAEDecode", "inputs": {"samples": ["edit_sample", 0], "vae": ["edit_vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_ABbg"}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    variant = sys.argv[1]
    seed = int(sys.argv[2])
    prompt_text = PROMPT_WITH_BACKGROUND if variant == "with" else PROMPT_WITHOUT_BACKGROUND
    graph = build(prompt_text, seed)
    with open(f"tests/router/runs/AB_bg_{variant}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "seed": seed, "filenames": filenames}, indent=2))
