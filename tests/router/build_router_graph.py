"""
V1 task router: one graph, one queue press. Analyzer emits structured JSON
-> task extracted -> deterministic lazy switch (no LLM-authored routing
decision, per the joint decision made during schema design) picks GENERATE
(Z-Image Turbo) or EDIT (Qwen Image Edit 2511) -> single SaveImage.

Built on everything validated earlier today: QwenVLStructuredGGUF (grammar-
constrained structured JSON), image_director.edit_plan_schema (schema
generation), the abliterated text encoder + Qwen Image Edit 2511 (both
runtime-smoke-tested), and "easy ifElse"'s lazy evaluation
(tests/router/RESULTS_lazy_switch.md - empirically confirmed the unused
branch's entire upstream chain, including model loads, is never scheduled).

Both branches decode to plain IMAGE before the switch (per Codex's
guidance - do not switch on MODEL/CONDITIONING/LATENT, only on the final
IMAGE, to avoid ComfyUI type-validation friction). Neither branch contains
an OUTPUT_NODE=True node (no branch-local SaveImage/PreviewImage) - that
would force the branch to execute as an execution root regardless of the
switch. Exactly one SaveImage after the merge.

Supports 0-2 reference images beyond the mandatory source (image1), via
`build(..., refs=[...])`. Availability-specific schema selection: the
schema's `reference_count` is picked from `len(refs)` at graph-build time,
matching the wiring pattern proven in
`tests/vram/combined-multiref/build_graph.py` (E2/E3, non-router path) -
extra LoadImage nodes, added as `image2`/`image3` to both the analyzer's
inputs and both `TextEncodeQwenImageEditPlus` nodes (pos + neg) in the
edit branch. VRAM-measured (cold-floor, n=1 per reference count) for
`refs` != []; see `tests/vram/router/RESULTS_RVref.md` - not yet measured
under back-to-back-without-`/free` sequencing.

Scheduling note: unlike the old prompt-only analyzer path, this router does
NOT need the E2/E3 StringSubstring dependency-injection fix for the
editor's negative prompt. The lazy switch's own boolean input is derived
from the analyzer's JSON output (via GetTextFromJson), so the edit branch's
nodes cannot even enter the pending execution set until the analyzer has
already finished - the routing architecture itself enforces sequential
analyzer-then-branch execution as a side effect, without an ad-hoc fix.
This is a design expectation, not yet independently re-measured with VRAM
timestamps the way E2/E3 was - flagged for the next validation pass.
"""
import json
import sys

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf"

GUIDANCE = """You are creating a structured plan for an image generation/editing pipeline. schema_version is always "1.0". If this is a text-to-image request unrelated to the attached image(s), use task="generate" - ignore the attached image(s) entirely in that case. If the request modifies the attached image, use task="edit": set is_local_region to true only if just one specific subject/region should change and everything else must stay the same (false if the whole image is being transformed/restyled), list "images" with image1 (role "source"){reference_note}, describe the needed edit(s), and list what must be preserved. For edits[]: only list things that actually change; use subject "entire image"/region "full image" only when no more specific subject exists; the prompt field must be one clean instruction for an image model, no markdown or commentary.

Instruction: {instruction}"""

REFERENCE_NOTE_BY_COUNT = {
    0: "",
    1: " plus image2 (a reference image - give it a role and use reference_slots on any edits[] entry that draws on it)",
    2: " plus image2 and image3 (reference images - give each a role and use reference_slots on any edits[] entry that draws on them)",
}


def edit_plan_schema_for(reference_count: int):
    sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director")
    from image_director.edit_plan_schema import edit_plan_schema
    return edit_plan_schema(source_image=True, reference_count=reference_count)


def build(instruction: str, seed: int, analyzer_seed: int, refs: list[str] | None = None) -> dict:
    refs = refs or []
    assert 0 <= len(refs) <= 2, "router supports 0-2 reference images (image2, image3)"

    prompt_text = GUIDANCE.format(instruction=instruction, reference_note=REFERENCE_NOTE_BY_COUNT[len(refs)])
    schema = edit_plan_schema_for(len(refs))

    graph = {
        # Source image, always loaded (cheap - see RESULTS_lazy_switch.md,
        # LoadImage alone leaves no observable execution-cost trace, no
        # need to gate it behind laziness).
        "src": {"class_type": "LoadImage", "inputs": {"image": "imgdir_jsontest_shapes.png"}},
    }
    for i, ref_file in enumerate(refs, start=2):
        graph[f"ref{i}"] = {"class_type": "LoadImage", "inputs": {"image": ref_file}}

    analyzer_inputs = {
        "model_path": MODEL_PATH,
        "mmproj_path": MMPROJ_PATH,
        "prompt": prompt_text,
        "json_schema": json.dumps(schema),
        "max_tokens": 512,
        "temperature": 0.1,
        "top_p": 0.9,
        "repetition_penalty": 1.2,
        "seed": analyzer_seed,
        "ctx": 8192,
        "gpu_layers": -1,
        "keep_model_loaded": False,
        # Router-only: back-to-back requests without /free were measured
        # to hit 901 MiB free VRAM here (RESULTS_RVchain.md) because this
        # node's llama.cpp load is invisible to comfy.model_management.
        "free_vram_before_load": True,
        "image": ["src", 0],
    }
    for i, _ in enumerate(refs, start=2):
        analyzer_inputs[f"image{i}"] = [f"ref{i}", 0]

    graph.update({
        # Analyzer -> structured JSON -> task/prompt extraction.
        "analyzer": {"class_type": "QwenVLStructuredGGUF", "inputs": analyzer_inputs},
        "plan_json": {"class_type": "LoadJsonFromText", "inputs": {"data": ["analyzer", 0]}},
        "task_str": {"class_type": "GetTextFromJson", "inputs": {"json": ["plan_json", 0], "key": "task"}},
        "edit_prompt_str": {"class_type": "GetTextFromJson", "inputs": {"json": ["plan_json", 0], "key": "prompt"}},
        "is_edit": {
            "class_type": "easy compare",
            "inputs": {"a": ["task_str", 0], "b": "edit", "comparison": "a == b"},
        },

        # GENERATE branch (Z-Image Turbo) - decodes to IMAGE, no output node.
        # NOTE: the official ComfyUI template (image_z_image_turbo.json)
        # names different files (z_image_turbo_bf16.safetensors,
        # qwen_3_4b.safetensors) that are NOT installed in this ComfyUI -
        # first submission attempt hit a real "Value not in list" validation
        # error from using those unverified template paths (see
        # RESULTS_router_v1.md). Corrected to the actually-installed files,
        # user's explicit choice: jibMixZIT_v10.safetensors (UNet, matches
        # the official template's UNETLoader/safetensors loader type) +
        # Lockout-Qwen3-4b-zimage-hereticV2 (CLIP, user's explicit choice -
        # GGUF is the only installed option for this text encoder at all).
        "gen_unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Z-Image Turbo\\jibMixZIT_v10.safetensors", "weight_dtype": "default"}},
        "gen_clip": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Z-Image Turbo\\Lockout-Qwen3-4b-zimage-hereticV2-q8.gguf", "type": "lumina2"}},
        "gen_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Flux.1 & Z-Image\\ae.safetensors"}},
        "gen_cond_pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["gen_clip", 0], "text": ["edit_prompt_str", 0]}},
        "gen_cond_neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["gen_cond_pos", 0]}},
        "gen_model": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["gen_unet", 0], "shift": 3}},
        "gen_latent": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "gen_sample": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["gen_model", 0], "positive": ["gen_cond_pos", 0], "negative": ["gen_cond_neg", 0],
                "latent_image": ["gen_latent", 0], "seed": seed, "steps": 8, "cfg": 1,
                "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1,
            },
        },
        "gen_image": {"class_type": "VAEDecode", "inputs": {"samples": ["gen_sample", 0], "vae": ["gen_vae", 0]}},

        # EDIT branch (Qwen Image Edit 2511) - decodes to IMAGE, no output node.
        # Negative prompt deliberately depends on edit_prompt_str (the
        # analyzer's own output) rather than a bare "" literal - keeps the
        # same real-dependency shape the E2/E3 fix required, even though
        # the lazy-switch design should already force sequential ordering
        # (see module docstring) - defense in depth, cheap to keep.
        "edit_unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen-image-edit-2511-Q4_K_M.gguf"}},
        "edit_clip": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "Qwen2.5-VL-7B-abliterated\\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf", "type": "qwen_image"}},
        "edit_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Qwen Image Edit 2509\\qwen_image_vae.safetensors"}},
        "edit_scale": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["src", 0]}},
        "edit_model": {"class_type": "CFGNorm", "inputs": {"model": ["edit_unet", 0], "strength": 1.0}},
        "edit_model_s": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["edit_model", 0], "shift": 3}},
        "edit_latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["edit_scale", 0], "vae": ["edit_vae", 0]}},
        "edit_cond_pos": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {"clip": ["edit_clip", 0], "vae": ["edit_vae", 0], "image1": ["edit_scale", 0], "prompt": ["edit_prompt_str", 0]},
        },
        "edit_neg_str": {"class_type": "StringSubstring", "inputs": {"string": ["edit_prompt_str", 0], "start": 0, "end": 0}},
        "edit_cond_neg": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {"clip": ["edit_clip", 0], "vae": ["edit_vae", 0], "image1": ["edit_scale", 0], "prompt": ["edit_neg_str", 0]},
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

        # Merge - single switch, single output.
        "switch": {"class_type": "easy ifElse", "inputs": {"boolean": ["is_edit", 0], "on_true": ["edit_image", 0], "on_false": ["gen_image", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["switch", 0], "filename_prefix": "ImageDirector_router"}},
    })

    for i, _ in enumerate(refs, start=2):
        graph["edit_cond_pos"]["inputs"][f"image{i}"] = [f"ref{i}", 0]
        graph["edit_cond_neg"]["inputs"][f"image{i}"] = [f"ref{i}", 0]

    return {"prompt": graph}


if __name__ == "__main__":
    instruction = sys.argv[1]
    seed = int(sys.argv[2])
    analyzer_seed = int(sys.argv[3])
    refs = sys.argv[4:]
    print(json.dumps(build(instruction, seed, analyzer_seed, refs=refs), ensure_ascii=False))
