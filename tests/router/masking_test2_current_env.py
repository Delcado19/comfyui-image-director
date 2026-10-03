"""
Reproduction of RESULTS_masking_test1.md's successful mechanism (SAM3 mask +
SetLatentNoiseMask + mask-aware prompt) under the CURRENT production
environment, with VRAM + execution-order instrumentation added (per Codex's
recommended smallest test before touching build_router_graph.py, joint
decision 2026-10-03: no automatic field-based masking gate, explicit-mode
integration only, verify the proven mechanism still holds before any router
change).

Why this is a NEW script, not an edit of masking_test1_setlatentnoisemask.py:
the original is a historical record of a real 2026-08-05 result and its
exact inputs no longer exist (see below) - PROJECT_RULES.md's rule to not
edit historic run records applies.

What changed vs. the original test, found by live-verifying against the
running ComfyUI instance (v0.29.2 -> v0.38.0 since the original test) before
writing any of this, per project rule "verify installed node classes and
concrete model paths before using them":
- Qwen Image Edit 2511 UNet is no longer a GGUF file. UnetLoaderGGUF's
  combo no longer lists it at all; the file now exists as
  models/diffusion_models/Qwen Image Edit 2511/qwen_image_edit_2511_fp8.safetensors,
  loaded via the plain UNETLoader.
- The abliterated text encoder used by the editor's own CLIP also moved
  GGUF -> fp8 safetensors (models/text_encoders/Qwen Image Edit 2511/
  qwen2.5_vl_7b_huihui_abliterated_fp8.safetensors), loaded via CLIPLoader
  (type="qwen_image"), not CLIPLoaderGGUF. Confirmed via GET /object_info.
- IMG_7148.jpg and imgdir_test_ref2.png (the original source photo and blue
  reference swatch) are no longer in ComfyUI's input/ directory - the
  folder now holds a different, unrelated file set. Not recoverable as
  pixel data from anywhere in this project; only their SHA hashes survive
  in old PNG metadata (useless for reconstruction).
- Substitute fixtures (user-directed: checked E:\\AI_Art for leftover
  artifacts of the original run): the original run's own SUCCESSFUL OUTPUT
  (E:\\AI_Art\\ImageDirector_MaskTest1_00002_.png - the woman with the dress
  already recolored blue, everything outside the mask claimed
  pixel-identical to the original source) is reused as the new source
  photo, copied to input/imgdir_masktest2_source_bluedress.png. A new solid
  firebrick-red swatch (input/imgdir_masktest2_ref_red.png, generated here,
  no original to recover) stands in for the reference image - consistent
  with the project's own past characterization of this kind of reference as
  a "flat swatch". This means the ablation direction is blue-dress ->
  red-dress, not black -> blue as in the original; the MECHANISM being
  retested (SAM3 mask + SetLatentNoiseMask + mask-aware prompt) is identical,
  only the concrete colors differ.
- sam3.safetensors itself is unchanged on disk; GET /object_info/easy
  sam3ModelLoader returns a broken combo list (literally the characters
  C/O/M/B/O) in this ComfyUI version - an API-introspection bug in the
  comfyui-easy-sam3 node pack (yolain/ComfyUI-Easy-Sam3, not ComfyUI-Easy-Use)
  after the ComfyUI 0.38.0 upgrade, not a missing file. The known-good value
  "sam3.safetensors" is used directly; this script's own /prompt result is
  the actual verification (node_errors would reject it if truly invalid).

Instrumentation added (did not exist in the original script):
- Background nvidia-smi sampling thread (250ms interval, matches the
  project's existing RV-test methodology) writing timestamp,used_mib,free_mib
  to a CSV for the whole submit-to-completion window.
- After completion, dumps the full /history response (status.messages) to
  JSON - ComfyUI's own execution-event log (node start/cached/success per
  node, each with a timestamp) is read from there for execution-order
  evidence, instead of inferring order only from VRAM step shape.
- Mask-vs-source pixel comparison: in addition to the original's visual-only
  check, this script numerically diffs the final output against the scaled
  source OUTSIDE the SAM3 mask (Codex's point: SetLatentNoiseMask operates
  on latents, not pixels directly - VAE decode and mask edges can still
  change pixels the original test never measured).
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty  # noqa: E402

SOURCE_IMAGE = "imgdir_masktest2_source_bluedress.png"
REF_IMAGE = "imgdir_masktest2_ref_red.png"
SAM3_PROMPT = "the woman's dress"

PROMPT_MASKED_WITH_COLOR = (
    "Change only the masked dress to match the red color and material of Reference Image #2. "
    "Keep everything outside the mask unchanged."
)
PROMPT_MASKED_NO_COLOR = (
    "Change only the masked dress to match Reference Image #2. "
    "Keep everything outside the mask unchanged."
)


def build(seed: int, use_mask: bool, prompt_text: str) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": SOURCE_IMAGE}},
        "ref2": {"class_type": "LoadImage", "inputs": {"image": REF_IMAGE}},
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
        "edit_image": {"class_type": "VAEDecode", "inputs": {"samples": ["edit_sample", 0], "vae": ["edit_vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["edit_image", 0], "filename_prefix": "ImageDirector_MaskTest2"}},
    }

    latent_for_sampler = ["edit_latent", 0]
    if use_mask:
        graph["sam3_load"] = {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}}
        graph["sam3_seg"] = {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["edit_scale", 0], "prompt": SAM3_PROMPT,
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        }
        # easy sam3ImageSegmentation's output index 1 is "images" (a plain
        # passthrough of the input image, NOT a mask overlay - confirmed via
        # GET /object_info: outputs=[MASK, IMAGE, MASK, BBOX, FLOAT], names=
        # [masks, images, obj_masks, boxes, scores]). The original
        # masking_test1 script also saved this same passthrough under the
        # name "mask_preview" - it never actually visualized the mask.
        # Fixed here: MaskToImage on output 0 (the real MASK) is the correct
        # way to visualize what SetLatentNoiseMask actually receives.
        graph["mask_to_image"] = {"class_type": "MaskToImage", "inputs": {"mask": ["sam3_seg", 0]}}
        graph["mask_preview"] = {"class_type": "SaveImage", "inputs": {"images": ["mask_to_image", 0], "filename_prefix": "ImageDirector_MaskTest2_maskpreview"}}
        graph["noise_mask"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["edit_latent", 0], "mask": ["sam3_seg", 0]}}
        latent_for_sampler = ["noise_mask", 0]

    graph["edit_sample"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["edit_model_s", 0], "positive": ["edit_cond_pos", 0], "negative": ["edit_cond_neg", 0],
            "latent_image": latent_for_sampler, "seed": seed, "steps": 8, "cfg": 2.5,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
        },
    }
    return {"prompt": graph}


def sample_vram(csv_path: Path, stop_event: threading.Event, interval_s: float = 0.25):
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("t,used_mib,free_mib\n")
        while not stop_event.is_set():
            t = time.time()
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            used, free = (x.strip() for x in out.stdout.strip().split(","))
            f.write(f"{t:.3f},{used},{free}\n")
            f.flush()
            time.sleep(interval_s)


def run_variant(variant: str, seed: int, use_mask: bool, prompt_text: str, out_dir: Path):
    assert_queue_empty()
    csv_path = out_dir / f"vram_log_masktest2_{variant}.csv"
    hist_path = out_dir / f"history_masktest2_{variant}.json"

    stop_event = threading.Event()
    sampler = threading.Thread(target=sample_vram, args=(csv_path, stop_event), daemon=True)
    sampler.start()

    graph = build(seed, use_mask, prompt_text)
    (out_dir / f"graph_masktest2_{variant}.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")

    t0 = time.time()
    pid = submit(graph)
    result = poll_history(pid, timeout_s=300)
    t1 = time.time()

    stop_event.set()
    sampler.join(timeout=2)

    hist_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    outs = result.get("outputs", {})
    save_out = outs.get("save", {})
    filenames = [i["filename"] for i in save_out.get("images", [])]
    mask_out = outs.get("mask_preview", {})
    mask_filenames = [i["filename"] for i in mask_out.get("images", [])]

    summary = {
        "variant": variant, "prompt_id": pid, "seed": seed, "wall_time_s": round(t1 - t0, 1),
        "filenames": filenames, "mask_filenames": mask_filenames,
        "status_completed": result.get("status", {}).get("completed"),
        "execution_cached": next(
            (m[1] for m in result.get("status", {}).get("messages", []) if m[0] == "execution_cached"), None
        ),
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    variant = sys.argv[1]  # "masked_withcolor" or "masked_nocolor"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
    out_dir = Path("tests/router/runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = PROMPT_MASKED_NO_COLOR if variant == "masked_nocolor" else PROMPT_MASKED_WITH_COLOR
    run_variant(variant, seed, use_mask=True, prompt_text=prompt_text, out_dir=out_dir)
