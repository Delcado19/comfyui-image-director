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

Editor model paths migrated 2026-10-03: ComfyUI was upgraded v0.29.2 ->
v0.38.0 during a ~2-month project pause, and the GGUF UNet/CLIP pair this
router used to load no longer exists on disk - both were replaced by fp8
safetensors files under the new diffusion_models/text_encoders folder
convention (GET /object_info live-verified, not assumed; see PROJECT_RULES.md's
2026-10-03 entry for the full before/after). edit_unet/edit_clip below now
use UNETLoader/CLIPLoader, not UnetLoaderGGUF/CLIPLoaderGGUF.

edit_mode parameter (added 2026-10-03, joint Claude-Codex decision, Codex
exec session, read-only review of this file + RESULTS_masking_test1.md +
RESULTS_masking_test2_current_env.md): "plain" (default) or
"masked_reference". "Unchanged" applies to the node SET and wiring only -
per Codex's post-implementation review, the GGUF->fp8 loader migration
above changes the actual model representation plain mode runs on, so this
is a same-shape-graph guarantee, not a no-change-at-all guarantee; plain
mode's own live validation (this session) is the only evidence it still
produces correct output. Deliberately NOT auto-selected from the
analyzer's structured plan - is_local_region/edits[].subject/.region are
documented (image_director/edit_plan_schema.py, RESULTS_analyzer_field_reliability*.md)
as too unreliable to gate rendering behavior. masked_reference requires the
CALLER to explicitly pass mask_target/reference_description - this is a
manually-selected graph variant, not automatic detection. Rejected
alternatives: (a) a 3-way runtime lazy switch gated on is_local_region -
rejected, elevates a known-unreliable field to a render-gating decision;
(b) always running SAM3+mask whenever task=edit and a reference image is
present - rejected, reference presence doesn't imply locality (a global
reference-based restyle would be masked incorrectly).

Known, OPEN (not Codex-blessed, documented by the implementing agent) risk:
the outer generate/edit lazy switch only guarantees the edit branch starts
after the analyzer - it does NOT guarantee SAM3's load and the editor's own
CLIP/UNet load are sequential *within* the masked edit branch, since
sam3_load/sam3_seg has no data dependency on edit_clip/edit_unet (unlike
E2/E3's negative-prompt fix, there is no cheap string-typed input here to
force one). Empirically fine in live n=1/n=2 samples (see
RESULTS_masking_test2_current_env.md), but the VRAM sampling loop used
there had actual gaps up to ~1.2-1.4s between samples (nvidia-smi subprocess
overhead, not a clean 250ms series despite that being the requested
interval) - the reported 760-888 MiB worst-sampled-margin figures are real
observed minimums, not a proven worst-case floor; a lower, unsampled trough
cannot be ruled out. Not proven to hold under back-to-back sequencing the
way the generate/edit switch itself was. Do not treat masked_reference as
cleared for back-to-back production use without a dedicated, tighter-
sampling VRAM-chain test (same category as the existing
back-to-back-without-/free mandatory-rule tests for the plain edit branch).
"""
import json
import sys

MODEL_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf"
MMPROJ_PATH = r"G:\ComfyUI-Easy-Install\ComfyUI\models\llm\GGUF\huihui-ai\Qwen2.5-VL-7B-Instruct-abliterated-GGUF\Qwen2.5-VL-7B-Instruct-abliterated.mmproj-f16.gguf"

MASKED_PROMPT_TEMPLATE = (
    "Change only the masked {target} to match the {description} of Reference Image #2. "
    "Keep everything outside the mask unchanged."
)

GUIDANCE = """You are creating a structured plan for an image generation/editing pipeline. schema_version is always "1.0". If this is a text-to-image request unrelated to the attached image(s), use task="generate" - ignore the attached image(s) entirely in that case. If the request modifies the attached image, use task="edit": set is_local_region to true only if just one specific subject/region should change and everything else must stay the same (false if the whole image is being transformed/restyled), list "images" with image1 (role "source"){reference_note}, describe the needed edit(s), and list what must be preserved. For edits[]: only list things that actually change; use subject "entire image"/region "full image" only when no more specific subject exists; the prompt field must be one clean instruction for an image model, no markdown or commentary.

Instruction: {instruction}"""

REFERENCE_NOTE_BY_COUNT = {
    0: "",
    1: " plus image2 (a reference image - give it a role and use reference_slots on any edits[] entry that draws on it)",
    2: " plus image2 and image3 (reference images - give each a role and use reference_slots on any edits[] entry that draws on them)",
}


def edit_plan_schema_for(reference_count: int):
    sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director")
    from image_director.edit_plan_schema import edit_plan_schema
    return edit_plan_schema(source_image=True, reference_count=reference_count)


def build(
    instruction: str, seed: int, analyzer_seed: int, refs: list[str] | None = None,
    *, edit_mode: str = "plain", mask_target: str | None = None, reference_description: str | None = None,
    source_image: str = "imgdir_jsontest_shapes.png",
) -> dict:
    # source_image parameter added 2026-10-03 (Codex post-implementation
    # review): the hardcoded default below no longer exists in ComfyUI's
    # input/ directory (deleted during the project's 2-month pause, see
    # PROJECT_RULES.md's 2026-10-03 entry) - every prior live validation of
    # this change overrode graph["prompt"]["src"]["inputs"]["image"] AFTER
    # calling build(), which never actually exercised this unmodified
    # return value. The default name is kept only for callers that already
    # have a file by that name; pass a real filename explicitly otherwise.
    refs = refs or []
    assert 0 <= len(refs) <= 2, "router supports 0-2 reference images (image2, image3)"
    assert edit_mode in ("plain", "masked_reference"), f"edit_mode must be 'plain' or 'masked_reference', got: {edit_mode!r}"
    if edit_mode == "masked_reference":
        assert len(refs) == 1, "masked_reference mode supports exactly 1 reference image (the proven RESULTS_masking_test1/2 setup - 'Reference Image #2' is hardcoded singular in the prompt template)"
        assert mask_target and mask_target.strip(), "masked_reference mode requires an explicit mask_target (the SAM3 segmentation prompt, e.g. 'the woman's dress') - not derived from the analyzer's plan, see module docstring"
        assert reference_description and reference_description.strip(), "masked_reference mode requires an explicit reference_description (e.g. 'red color and material') - the one tested color-free wording failed to transfer the reference's color, see RESULTS_masking_test2_current_env.md's ablation"

    prompt_text = GUIDANCE.format(instruction=instruction, reference_note=REFERENCE_NOTE_BY_COUNT[len(refs)])
    schema = edit_plan_schema_for(len(refs))

    graph = {
        # Source image, always loaded (cheap - see RESULTS_lazy_switch.md,
        # LoadImage alone leaves no observable execution-cost trace, no
        # need to gate it behind laziness).
        "src": {"class_type": "LoadImage", "inputs": {"image": source_image}},
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
        # LoadJsonFromText/GetTextFromJson (comfyui-art-venture) were found
        # quarantine-disabled 2026-10-03 (custom_nodes/_quarantine.disabled/
        # comfyui-art-venture) - not re-enabled without asking why it was
        # quarantined. Replaced with the core ComfyUI node JsonExtractString
        # (comfy_extras/nodes_string.py, added to core sometime during the
        # v0.29.2->v0.38.0 upgrade this project pause spanned), which reads
        # a key directly from a JSON string in one node - no separate
        # "load" step needed, one fewer node per extraction than before.
        # Caveat (Codex review): invalid JSON or a missing key silently
        # yields "" rather than raising - task_str=="" falls through to the
        # generate branch via "is_edit" below rather than erroring. Not
        # observed in any live run so far; not independently verified
        # against the old LoadJsonFromText/GetTextFromJson pair's own
        # failure behavior either.
        "analyzer": {"class_type": "QwenVLStructuredGGUF", "inputs": analyzer_inputs},
        "task_str": {"class_type": "JsonExtractString", "inputs": {"json_string": ["analyzer", 0], "key": "task"}},
        "edit_prompt_str": {"class_type": "JsonExtractString", "inputs": {"json_string": ["analyzer", 0], "key": "prompt"}},
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
        # gen_clip/gen_vae paths fixed 2026-10-03 (same environment drift as
        # the edit branch - see module docstring): the GGUF CLIP is gone
        # (only a safetensors Lockout build remains, folder renamed
        # Z-Image Turbo -> Z-Image), and the VAE's containing folder was
        # renamed Flux.1 & Z-Image -> Flux.1 - Z-Image - HiDream. Both
        # verified live via GET /object_info, same file content otherwise.
        "gen_unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Z-Image Turbo\\jibMixZIT_v10.safetensors", "weight_dtype": "default"}},
        "gen_clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Z-Image\\Lockout-Qwen3-4b-heretic-v2.safetensors", "type": "lumina2"}},
        "gen_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "Flux.1 - Z-Image - HiDream\\ae.safetensors"}},
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
        # fp8 safetensors, not GGUF - see module docstring's 2026-10-03 note.
        "edit_unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen_image_edit_2511_fp8.safetensors", "weight_dtype": "default"}},
        "edit_clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "Qwen Image Edit 2511\\qwen2.5_vl_7b_huihui_abliterated_fp8.safetensors", "type": "qwen_image"}},
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

    if edit_mode == "masked_reference":
        # SAM3 mask -> SetLatentNoiseMask, mechanism proven in
        # RESULTS_masking_test1.md and reproduced under the current
        # environment in RESULTS_masking_test2_current_env.md. Deliberately
        # NO SaveImage on sam3_seg's output here (unlike the standalone test
        # scripts' "mask_preview" node) - an OUTPUT_NODE=True node here would
        # force SAM3 to execute even when the generate branch is selected,
        # breaking the lazy-switch property this module's docstring requires.
        # Inspect the mask via the standalone masking_test2_current_env.py
        # script instead, not via this production graph.
        graph["sam3_load"] = {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}}
        graph["sam3_seg"] = {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["edit_scale", 0], "prompt": mask_target,
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        }
        graph["noise_mask"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["edit_latent", 0], "mask": ["sam3_seg", 0]}}
        graph["edit_sample"]["inputs"]["latent_image"] = ["noise_mask", 0]

        # Positive prompt overridden with the proven mask-aware template
        # instead of the analyzer's free-form edit_prompt_str - see module
        # docstring: today's reproduction's specific reworded, color-name-
        # free prompt variant failed to transfer the reference's color
        # (RESULTS_masking_test2_current_env.md's ablation) - not a clean
        # single-variable isolation (the reworded variant also dropped
        # "and material" and changed other phrasing), so treat this as "the
        # tested alternative wording failed," not a general proof that no
        # color-free wording could ever work.
        # Negative prompt is left on its existing edit_prompt_str dependency
        # (unrelated to masking, keeps the E2/E3-style scheduling guard).
        graph["masked_prompt_literal"] = {
            "class_type": "PrimitiveString",
            "inputs": {"value": MASKED_PROMPT_TEMPLATE.format(target=mask_target, description=reference_description)},
        }
        graph["edit_cond_pos"]["inputs"]["prompt"] = ["masked_prompt_literal", 0]

    return {"prompt": graph}


if __name__ == "__main__":
    instruction = sys.argv[1]
    seed = int(sys.argv[2])
    analyzer_seed = int(sys.argv[3])
    refs = sys.argv[4:]
    print(json.dumps(build(instruction, seed, analyzer_seed, refs=refs), ensure_ascii=False))
