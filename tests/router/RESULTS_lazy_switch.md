# Lazy-switch mechanism probe - result

**PASS, both directions.** `easy ifElse` (ComfyUI-Easy-Use) correctly skips
the entire unused branch's execution, not just the final node's read of
that input - confirmed empirically through the real ComfyUI queue, not
just from source reading.

## Method

Two branches with genuinely different, externally observable cost:
`on_true` = `PrimitiveString` (instant, no loading, no log trace),
`on_false` = `AILab_QwenVL_GGUF_Advanced` (the analyzer, several seconds,
prints a distinctive `[QwenVL] Loading GGUF: ...` log line,
`keep_model_loaded=false`). Exactly one `PreviewAny` after the switch - no
`OUTPUT_NODE=True` inside either branch, per Codex's warning that an
output node inside a branch would force it to execute as an execution
root regardless of the switch.

Ran twice, checking wall time, whether the GGUF-loading log line appeared
in the log lines written during that specific run, and the actual output
value.

## Results

| Run | Analyzer wired to | `boolean` | Wall time | GGUF load line seen | Output |
|---|---|---|---|---|---|
| 1 | `on_false` | `true` | 1.23s | **no** | `"CHEAP_TRUE_BRANCH_MARKER"` |
| 2 | `on_false` | `false` | 5.08s | **yes** | `"The shape is a purple star."` |
| 3 | `on_true` | `false` | 0.45s | **no** | `"CHEAP_FALSE_BRANCH_MARKER"` |

Run 1: fast, no trace of the analyzer branch at all, correct cheap-branch
value returned - the ~5GB GGUF model was never loaded.
Run 2: slower (model load + real vision inference), GGUF load line present,
analyzer's real output returned, correctly describing the actual image
content.
Run 3 (added per Codex's review - runs 1+2 alone only proved `on_false`
skips/executes correctly, not `on_true`; this mirrors the wiring, putting
the analyzer on `on_true` instead): fast, no GGUF load line, correct
cheap-branch value - confirms `on_true` is skipped just as reliably as
`on_false` when unselected. Both input slots now independently verified in
both directions.

## What this settles

- ComfyUI's lazy evaluation (`lazy=True` input + `check_lazy_status`) does
  what the source code claims: the unused branch's entire upstream
  dependency chain (here, a multi-second model load) is never scheduled,
  not merely "computed but discarded." This was independently confirmed by
  reading `comfy_execution/graph.py`'s `TopologicalSort.add_node()`
  (`include_lazy=False` skips lazy-input upstream chains when building the
  initial pending-node set) and by Codex's independent trace through
  `execution.py`'s `check_lazy_status`/`make_input_strong_link` handling -
  now also confirmed empirically, not just from source.
- `easy ifElse` is validated as the routing mechanism for the actual
  router: pick exactly one of two expensive branches (Z-Image Turbo vs
  Qwen Image Edit 2511), without paying the cost of the unselected one.

## What this does not settle

- The real router's branches (Z-Image Turbo, Qwen Image Edit 2511) are
  much more expensive and structurally different (multiple models, VAE,
  sampler chains) than this probe's stand-ins - this proves the mechanism
  works for a "one loader-shaped node vs one trivial node" case, not that
  the full real router graph will be free of some other issue (e.g. VRAM
  from validation-time model-path resolution, or type-compatibility
  friction wiring two different node families' outputs into one `easy
  ifElse`).
- Per Codex: validation is NOT lazy - both branches must still be
  structurally valid (real node classes, valid links, required inputs
  present, valid model paths) even though only one executes. Not
  specifically re-tested here beyond this probe's own two simple branches
  validating fine.
