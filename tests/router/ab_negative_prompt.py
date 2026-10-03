"""
Scoped experiment (Codex-designed, thread 019fcb5f-8503-7641-85a0-f7a74b1b7659):
does a real (non-empty) negative prompt help Qwen Image Edit 2511 keep a
reference-based garment recolor localized, instead of bleeding onto the
scene/background? Follow-up to RESULTS_ab_background_word.md's confirmed
finding and the failed guidance-clause fix attempt.

Currently `edit_cond_neg` in build_router_graph.py is ALWAYS an empty
string (StringSubstring(edit_prompt_str, 0, 0)) - dead weight, not steering
anything. This test checks whether a hand-written negative prompt (not yet
`preserve[]` from the analyzer - Codex's guidance: don't wire raw,
analyzer-generated preserve[] into production before checking negative
conditioning helps AT ALL for this failure mode) changes the outcome.

Two phases (results: RESULTS_ab_negative_prompt.md):
1. Non-regression check: positive prompt held fixed to the "good" literal
   from the background-word A/B test (no "background" clause). Only the
   negative prompt varies: empty (matches current router behavior) vs.
   hand-written (Codex's suggested list: "background, sky, buildings,
   pavement, environment, skin, hair, pose, face"). Pass condition (Codex):
   dress recolors AND background does not change.
2. Rescue test (optional 3rd CLI arg "bad"): positive prompt swapped to the
   confirmed-bleed wording (RESULTS_ab_background_word.md), same negative
   variants, to see if a real negative prompt suppresses the bleed the
   guidance-clause fix (build_router_graph.py, reverted) failed to prevent.

Fail if dress stops changing or the subject visibly degrades.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history

POSITIVE_PROMPT_GOOD = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue. The rest should remain unchanged."
)
# Same wording as RESULTS_ab_background_word.md's confirmed-bad variant, for the
# rescue test: can a real negative prompt suppress the bleed this wording causes?
POSITIVE_PROMPT_BAD = (
    "The woman is wearing a black leather dress that needs to be changed to match the color "
    "from Reference Image #2, which appears as a solid blue background. The rest should remain unchanged."
)
NEGATIVE_EMPTY = ""
NEGATIVE_HANDWRITTEN = "background, sky, buildings, pavement, environment, skin, hair, pose, face"


def build(positive_prompt: str, negative_prompt: str, seed: int) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": "IMG_7148.jpg"}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref2.png"}},
        "pos_literal": {"class_type": "PrimitiveString", "inputs": {"value": positive_prompt}},
        "neg_literal": {"class_type": "PrimitiveString", "inputs": {"value": negative_prompt}},

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
                "prompt": ["pos_literal", 0],
            },
        },
        "edit_cond_neg": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["edit_clip", 0], "vae": ["edit_vae", 0],
                "image1": ["edit_scale", 0], "image2": ["ref2", 0],
                "prompt": ["neg_literal", 0],
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
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_ABneg"}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    # variant: "empty"|"handwritten" negative. Optional 3rd arg "bad" switches the
    # positive prompt to the confirmed-bleed wording, for the rescue test Codex
    # proposed after the first run showed no visible negative-prompt effect on the
    # already-good positive (thread 019fd14f-0515-7a91-958a-ce162f468ce2).
    variant = sys.argv[1]
    seed = int(sys.argv[2])
    use_bad_positive = len(sys.argv) > 3 and sys.argv[3] == "bad"
    positive_prompt = POSITIVE_PROMPT_BAD if use_bad_positive else POSITIVE_PROMPT_GOOD
    negative_prompt = NEGATIVE_EMPTY if variant == "empty" else NEGATIVE_HANDWRITTEN
    run_tag = f"{variant}_bad" if use_bad_positive else variant
    graph = build(positive_prompt, negative_prompt, seed)
    with open(f"tests/router/runs/AB_neg_{run_tag}.graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    pid = submit(graph)
    result = poll_history(pid)
    outs = result["outputs"]
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    print(json.dumps({"prompt_id": pid, "variant": variant, "seed": seed, "filenames": filenames}, indent=2))
