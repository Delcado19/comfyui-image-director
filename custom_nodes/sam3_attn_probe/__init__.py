"""
Stage-1 probe for the SAM3-as-attention-hint spike (case 3 reference-bleed,
see comfyui-image-director's tests/router/RESULTS_ref_weight.md and
RESULTS_flux2dev_capability.md for the investigation that led here).

Purpose: verify the patches_replace["dit"][("double_block", i)] block-replace
hook (comfy/ldm/qwen_image/model.py:528-533, comfy/model_patcher.py:622)
fires with the expected contract on Qwen Image Edit 2511, WITHOUT touching
the ComfyUI installation - this node registers the patch at runtime via the
official ModelPatcher API on a cloned model. Logs shapes/keys once per run,
then calls through to the original block unchanged. No bias, no SAM3 input
yet - that's stage 2/3 of the spike, only built if this stage confirms the
hook contract matches what was read from source.
"""
import json
import os

DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "last_probe_log.json")


class QwenBlockPatchLoggerProbe:
    """Registers a logging-only patches_replace hook on one Qwen double_block."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "block_index": ("INT", {"default": 10, "min": 0, "max": 59, "step": 1}),
            }
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "ImageDirector/probe"

    def patch(self, model, block_index):
        m = model.clone()
        logged = {"done": False}

        def block_wrap_logger(args, extra_args):
            if not logged["done"]:
                logged["done"] = True
                to = args.get("transformer_options", {})
                pe = args.get("pe")
                info = {
                    "block_index": block_index,
                    "args_keys": list(args.keys()),
                    "img_shape": list(args["img"].shape),
                    "txt_shape": list(args["txt"].shape),
                    "vec_shape": list(args["vec"].shape),
                    "pe_type": str(type(pe)),
                    "pe_shape": list(pe.shape) if hasattr(pe, "shape") else (
                        [list(p.shape) for p in pe] if isinstance(pe, (tuple, list)) else None
                    ),
                    "transformer_options_keys": list(to.keys()),
                    "total_blocks": to.get("total_blocks"),
                    "block_type": to.get("block_type"),
                    "block_index_opt": to.get("block_index"),
                    "img_slice": to.get("img_slice"),
                    "reference_image_num_tokens": to.get("reference_image_num_tokens"),
                }
                print(f"[sam3_attn_probe] {json.dumps(info)}")
                with open(DEBUG_LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=2)
            original_block = extra_args["original_block"]
            return original_block(args)

        m.set_model_patch_replace(block_wrap_logger, "dit", "double_block", block_index)

        to = m.model_options.get("transformer_options", {})
        pr = to.get("patches_replace", {})
        dit = pr.get("dit", {})
        reg_info = {
            "model_class": type(m.model).__name__,
            "diffusion_model_class": type(getattr(m.model, "diffusion_model", None)).__name__,
            "registered_dit_keys": [str(k) for k in dit.keys()],
            "target_key_present": ("double_block", block_index) in dit,
            "model_options_top_keys": list(m.model_options.keys()),
        }
        print(f"[sam3_attn_probe] REGISTRATION: {json.dumps(reg_info)}")
        reg_path = os.path.join(os.path.dirname(__file__), "last_registration_log.json")
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(reg_info, f, indent=2)

        return (m,)


NODE_CLASS_MAPPINGS = {
    "QwenBlockPatchLoggerProbe": QwenBlockPatchLoggerProbe,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "QwenBlockPatchLoggerProbe": "Qwen Block Patch Logger (Probe)",
}
