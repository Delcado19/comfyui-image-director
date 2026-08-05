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

import torch

from comfy.ldm.modules.attention import optimized_attention_masked
from comfy.ldm.flux.math import apply_rope1

DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "last_probe_log.json")
REIMPL_LOG_PATH = os.path.join(os.path.dirname(__file__), "last_reimpl_log.json")


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


class QwenBlockAttnReimplProbe:
    """Stage 2: replaces one Qwen double_block's attn.forward with a hand-copied
    reimplementation (comfy/ldm/qwen_image/model.py's Attention.forward,
    ~lines 142-203), via ModelPatcher.add_object_patch - the official,
    reversible per-clone mechanism (comfy.utils.set_attr/object_patches_backup),
    NOT a permanent monkeypatch of the shared nn.Module. No bias applied yet;
    this only proves the reimplementation is faithful before Stage 3 adds a
    SAM3-mask-derived bias at the one line that matters
    (optimized_attention_masked's attn_mask argument)."""

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
        attn = m.model.diffusion_model.transformer_blocks[block_index].attn
        logged = {"done": False}

        def custom_attn_forward(hidden_states, encoder_hidden_states=None, encoder_hidden_states_mask=None,
                                 image_rotary_emb=None, transformer_options={}):
            batch_size = hidden_states.shape[0]
            seq_img = hidden_states.shape[1]
            seq_txt = encoder_hidden_states.shape[1]

            transformer_patches = transformer_options.get("patches", {})
            extra_options = transformer_options.copy()

            img_query = attn.to_q(hidden_states).view(batch_size, seq_img, attn.heads, -1).transpose(1, 2).contiguous()
            img_key = attn.to_k(hidden_states).view(batch_size, seq_img, attn.heads, -1).transpose(1, 2).contiguous()
            img_value = attn.to_v(hidden_states).view(batch_size, seq_img, attn.heads, -1).transpose(1, 2)

            txt_query = attn.add_q_proj(encoder_hidden_states).view(batch_size, seq_txt, attn.heads, -1).transpose(1, 2).contiguous()
            txt_key = attn.add_k_proj(encoder_hidden_states).view(batch_size, seq_txt, attn.heads, -1).transpose(1, 2).contiguous()
            txt_value = attn.add_v_proj(encoder_hidden_states).view(batch_size, seq_txt, attn.heads, -1).transpose(1, 2)

            img_query = attn.norm_q(img_query)
            img_key = attn.norm_k(img_key)
            txt_query = attn.norm_added_q(txt_query)
            txt_key = attn.norm_added_k(txt_key)

            joint_query = torch.cat([txt_query, img_query], dim=2)
            joint_key = torch.cat([txt_key, img_key], dim=2)
            joint_value = torch.cat([txt_value, img_value], dim=2)

            if encoder_hidden_states_mask is not None:
                attn_mask = torch.zeros((batch_size, 1, seq_txt + seq_img), dtype=hidden_states.dtype, device=hidden_states.device)
                attn_mask[:, 0, :seq_txt] = encoder_hidden_states_mask
            else:
                attn_mask = None

            extra_options["img_slice"] = [txt_query.shape[2], joint_query.shape[2]]
            if "attn1_patch" in transformer_patches:
                for p in transformer_patches["attn1_patch"]:
                    out = p(joint_query, joint_key, joint_value, pe=image_rotary_emb,
                             attn_mask=encoder_hidden_states_mask, extra_options=extra_options)
                    joint_query, joint_key, joint_value, image_rotary_emb, encoder_hidden_states_mask = (
                        out.get("q", joint_query), out.get("k", joint_key), out.get("v", joint_value),
                        out.get("pe", image_rotary_emb), out.get("attn_mask", encoder_hidden_states_mask),
                    )

            joint_query = apply_rope1(joint_query, image_rotary_emb)
            joint_key = apply_rope1(joint_key, image_rotary_emb)

            if not logged["done"]:
                logged["done"] = True
                info = {
                    "block_index": block_index,
                    "mode": "reimpl-no-bias",
                    "joint_query_shape": list(joint_query.shape),
                    "attn_mask_is_none": attn_mask is None,
                }
                print(f"[sam3_attn_probe] REIMPL: {json.dumps(info)}")
                with open(REIMPL_LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=2)

            joint_hidden_states = optimized_attention_masked(
                joint_query, joint_key, joint_value, attn.heads, attn_mask,
                transformer_options=transformer_options, skip_reshape=True,
            )

            txt_attn_output = joint_hidden_states[:, :seq_txt, :]
            img_attn_output = joint_hidden_states[:, seq_txt:, :]

            img_attn_output = attn.to_out[0](img_attn_output)
            img_attn_output = attn.to_out[1](img_attn_output)
            txt_attn_output = attn.to_add_out(txt_attn_output)

            return img_attn_output, txt_attn_output

        m.add_object_patch(f"diffusion_model.transformer_blocks.{block_index}.attn.forward", custom_attn_forward)
        return (m,)


NODE_CLASS_MAPPINGS = {
    "QwenBlockPatchLoggerProbe": QwenBlockPatchLoggerProbe,
    "QwenBlockAttnReimplProbe": QwenBlockAttnReimplProbe,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "QwenBlockPatchLoggerProbe": "Qwen Block Patch Logger (Probe)",
    "QwenBlockAttnReimplProbe": "Qwen Block Attn Reimpl (Probe, Stage 2)",
}
