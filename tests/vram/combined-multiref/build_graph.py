"""
Build the E2/E3 combined-multireference smoke-test graph.

This is a direct extension of the Test C graph documented in
docs/source/IMAGE_DIRECTOR_AUDIT.md SS13 (analyzer -> editor, one graph, one
queue press). The intended change from Test C is only the number of
reference images fed to the editor's TextEncodeQwenImageEditPlus node
(n_images=2 for E2, n_images=3 for E3). Every other node, model, and
parameter is held at Test C's / Test B's values, EXCEPT the analyzer's own
`seed` (see `analyzer_seed` below), which is deliberately varied per run to
avoid ComfyUI's node-output cache silently skipping the analyzer's
execution on a server where it already ran once with default settings
(see TESTPLAN.md, "Node-cache bust"). Topology otherwise copied from the
installed official image_qwen_image_edit_2509.json template via Test B/D's
own builder script.

Node "4" (LoadImage of imgdir_test_source.png) is reused for both the
analyzer's own image input and (after FluxKontextImageScale) the editor's
image1, matching Test C's ~13-node graph size (one LoadImage per unique
file, not one per consumer).
"""
import json
import sys


def build(n_images: int, prefix: str, analyzer_seed: int, steps: int = 8, cfg: float = 2.5,
          force_negative_dependency: bool = False):
    assert n_images in (2, 3), "E2/E3 only use 2 or 3 reference images"

    graph = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "Qwen Image Edit 2511\\qwen_image_edit_2511_fp8.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "Qwen Image Edit 2511\\qwen2.5_vl_7b_huihui_abliterated_fp8.safetensors",
                "type": "qwen_image",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "Qwen Image Edit 2509\\qwen_image_vae.safetensors"},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": "imgdir_test_source.png"},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": "imgdir_test_ref2.png"},
        },
        "7": {
            "class_type": "FluxKontextImageScale",
            "inputs": {"image": ["4", 0]},
        },
        "10": {
            "class_type": "CFGNorm",
            "inputs": {"model": ["1", 0], "strength": 1.0},
        },
        "11": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["10", 0], "shift": 3},
        },
        "12": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["7", 0], "vae": ["3", 0]},
        },
        "14": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["13", 0], "vae": ["3", 0]},
        },
        "15": {
            "class_type": "SaveImage",
            "inputs": {"images": ["14", 0], "filename_prefix": prefix},
        },
        # Analyzer: same node + settings as Test A/C. keep_model_loaded=false
        # is a mandatory rule for this test (PROJECT_RULES.md), not left at
        # the node's own default (true).
        "16": {
            "class_type": "AILab_QwenVL_GGUF_Advanced",
            "inputs": {
                "model_name": "Qwen2.5-VL-7B-Instruct-abliterated.Q4_K_M.gguf",
                "device": "auto",
                "preset_prompt": "\U0001f5bc️ Detailed Description",
                "custom_prompt": "",
                "max_tokens": 512,
                "temperature": 0.6,
                "top_p": 0.9,
                "repetition_penalty": 1.2,
                "frame_count": 16,
                "ctx": 8192,
                "n_batch": 512,
                "gpu_layers": -1,
                "image_max_tokens": 4096,
                "top_k": 0,
                "pool_size": 4194304,
                "keep_model_loaded": False,
                # Deliberately distinct per test run (not the node default),
                # to force a fresh execution instead of ComfyUI's node-output
                # cache reusing a prior run's result on identical inputs -
                # see TESTPLAN.md "cache" note. Does not affect the VRAM
                # measurement; only guarantees the analyzer actually runs.
                "seed": analyzer_seed,
                "image": ["4", 0],
            },
        },
    }

    pos_inputs = {
        "clip": ["2", 0],
        "vae": ["3", 0],
        "image1": ["7", 0],
        "image2": ["5", 0],
        # Positive prompt comes from the analyzer's own text output, exactly
        # as Test C wired it - not a hardcoded string.
        "prompt": ["16", 0],
    }
    neg_inputs = {
        "clip": ["2", 0],
        "vae": ["3", 0],
        "image1": ["7", 0],
        "image2": ["5", 0],
        "prompt": "",
    }

    if force_negative_dependency:
        # E2/E3 root-cause fix (Codex proposal, joint-reviewed after E3):
        # node 8 (negative encode) previously had no dependency on the
        # analyzer (node 16), so ComfyUI's executor was free to schedule it
        # - and load the editor's own CLIP - before or during the analyzer's
        # run, defeating the sequential "analyzer fully first, then editor"
        # architecture. StringSubstring(analyzer_text, 0, 0) always returns
        # "" (plain Python slicing), so the negative prompt is unchanged,
        # but node 8 now has a real data dependency on node 16 and cannot be
        # scheduled before it.
        graph["17"] = {
            "class_type": "StringSubstring",
            "inputs": {"string": ["16", 0], "start": 0, "end": 0},
        }
        neg_inputs["prompt"] = ["17", 0]

    if n_images == 3:
        graph["6"] = {"class_type": "LoadImage", "inputs": {"image": "imgdir_test_ref3.png"}}
        pos_inputs["image3"] = ["6", 0]
        neg_inputs["image3"] = ["6", 0]

    graph["8"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": neg_inputs}
    graph["9"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": pos_inputs}
    graph["13"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["11", 0],
            "positive": ["9", 0],
            "negative": ["8", 0],
            "latent_image": ["12", 0],
            "seed": 12345,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
        },
    }

    return {"prompt": graph}


if __name__ == "__main__":
    n = int(sys.argv[1])
    prefix = sys.argv[2]
    analyzer_seed = int(sys.argv[3])
    fixed = len(sys.argv) > 4 and sys.argv[4] == "fixed"
    print(json.dumps(build(n, prefix, analyzer_seed, force_negative_dependency=fixed), ensure_ascii=False))
