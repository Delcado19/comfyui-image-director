"""
One-off, standalone: generates a SAM3 "the woman's dress" mask for each
source image used by qwen21_integration_test2.py, purely for the numeric
locality check (qwen21_locality_numeric.py) - NOT part of the
editor="qwen_image21" router path, which uses no mask at all (that is the
entire point of the mechanism). Same SAM3 node/settings as the
masked_reference editors (easy sam3ModelLoader/easy sam3ImageSegmentation),
reused here only as an external measurement tool to define "outside the
dress region" for scoring, same role a human-drawn mask would play.
"""
import json
import sys

sys.path.insert(0, r"C:\Users\Delcado\Documents\Software_Projects\ComfyUI\comfyui-image-director\tests\lib")
from comfy_submit import submit, poll_history, assert_queue_empty, free  # noqa: E402

SOURCES = {
    "bluedress": "imgdir_masktest2_source_bluedress.png",
    "blackdress": "imgdir_casetest3_source_blackdress_cannes.png",
}


def build(source_image: str) -> dict:
    graph = {
        "src": {"class_type": "LoadImage", "inputs": {"image": source_image}},
        "sam3_load": {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}},
        "sam3_seg": {
            "class_type": "easy sam3ImageSegmentation",
            "inputs": {
                "sam3_model": ["sam3_load", 0], "images": ["src", 0], "prompt": "the woman's dress",
                "threshold": 0.3, "keep_model_loaded": False, "add_background": "none", "detection_limit": -1,
            },
        },
        "mask_preview": {"class_type": "MaskToImage", "inputs": {"mask": ["sam3_seg", 0]}},
        "mask_save": {"class_type": "SaveImage", "inputs": {"images": ["mask_preview", 0], "filename_prefix": "ImageDirector_Qwen21Locality_mask"}},
    }
    return {"prompt": graph}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = SOURCES.items() if which == "all" else [(which, SOURCES[which])]
    results = {}
    for name, source_image in targets:
        assert_queue_empty()
        free()
        pid = submit(build(source_image))
        result = poll_history(pid, timeout_s=120)
        outs = result.get("outputs", {})
        filenames = [i["filename"] for i in outs.get("mask_save", {}).get("images", [])]
        results[name] = {"status_completed": result.get("status", {}).get("completed"), "filenames": filenames}
    print(json.dumps(results, indent=2))
