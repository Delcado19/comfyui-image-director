"""
Numeric locality check for editor="qwen_image21" / edit_mode="native_reference",
matching RESULTS_flux2dev_masking_test1.md's methodology (per-pixel
max-channel absolute diff, restricted outside a mask, reported as
mean/p99/max/% px > 10/% px > 25) - with one adaptation, stated explicitly:

Dev/Klein diff against a pure VAEEncode->VAEDecode "baseline" (they anchor
sampling on the source's own latent, so a VAE round-trip is the right
reconstruction floor). TextEncodeQwenImage21 samples from a fully empty
latent (see qwen_image21_reference_test1.py's docstring) - there is no
VAE-anchored baseline to diff against; a VAE round-trip of the source is
not even part of this mechanism's own graph. The right comparator is each
run's own D variant (no reference attached, same seed, same source) - the
model's own "preserve everything, nothing to transfer" output - matching
how D was already used as the visual ablation baseline throughout
RESULTS_qwen_image21_reference_test1.md. This diffs B/B2/M against D at the
same seed, not against a VAE reconstruction.

The "outside the dress region" mask does not come from the router path
itself (editor="qwen_image21" uses no mask) - qwen21_mask_gen.py generates
it once per source image, standalone, purely as a measurement tool.
"""
import io
import json
import sys
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

# No local filesystem path is assumed for ComfyUI's output directory (the
# configured path does not match the default G:\...\ComfyUI\output - see
# this session's history of fetching results via /view instead). Every
# image is fetched through the same HTTP API the router submission itself
# uses, same base as comfy_submit.py.
BASE = "http://127.0.0.1:8188"


def fetch(filename: str) -> Image.Image:
    with urllib.request.urlopen(f"{BASE}/view?filename={urllib.parse.quote(filename)}&type=output", timeout=30) as r:
        return Image.open(io.BytesIO(r.read()))


def load_rgb(filename: str) -> np.ndarray:
    return np.asarray(fetch(filename).convert("RGB"), dtype=np.int16)


def load_outside_mask(mask_filename: str, target_size: tuple[int, int]) -> np.ndarray:
    """True where OUTSIDE the dress (mask_preview is white=dress, black=background).

    The mask is generated from the SOURCE image's native resolution
    (qwen21_mask_gen.py), but TextEncodeQwenImage21 internally resizes
    every image to ~1024px-ish (multiples of 32, aspect preserved) before
    sampling - the edit/baseline outputs are therefore a slightly
    different size than the mask. Resized here with NEAREST (binary mask,
    no interpolation blur) to the edit output's exact size.
    """
    mask_img = fetch(mask_filename).convert("L").resize(target_size, Image.NEAREST)
    return np.asarray(mask_img) < 128


def diff_stats(edit_filename: str, baseline_filename: str, mask_filename: str) -> dict:
    a = load_rgb(edit_filename)
    b = load_rgb(baseline_filename)
    assert a.shape == b.shape, f"shape mismatch: {a.shape} vs {b.shape}"
    # PIL size is (width, height); numpy shape is (height, width, ...).
    outside_mask = load_outside_mask(mask_filename, (a.shape[1], a.shape[0]))
    per_px_max_channel_diff = np.abs(a - b).max(axis=2)
    vals = per_px_max_channel_diff[outside_mask]
    return {
        "n_px": int(vals.size),
        "mean": round(float(vals.mean()), 2),
        "p99": round(float(np.percentile(vals, 99)), 1),
        "max": int(vals.max()),
        "pct_gt_10": round(float((vals > 10).mean() * 100), 2),
        "pct_gt_25": round(float((vals > 25).mean() * 100), 2),
    }


if __name__ == "__main__":
    # filename, filename, filename triples passed as JSON on argv[1]:
    # {"label": [edit_filename, baseline_filename, mask_filename], ...}
    pairs = json.loads(sys.argv[1])
    results = {label: diff_stats(edit_fn, baseline_fn, mask_fn) for label, (edit_fn, baseline_fn, mask_fn) in pairs.items()}
    print(json.dumps(results, indent=2))
