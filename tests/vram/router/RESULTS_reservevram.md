# `--reserve-vram` mitigation for the edit-branch VRAM margin — result

Tests the deferred lowvram/`--reserve-vram` direction noted in
`RESULTS_RVfix.md`/`RESULTS_RVrefchain.md` as "a candidate future
direction... needs its own measured pass, not assumed syntax." Per
Codex's guidance, verified the actual mechanism from source before
proposing any value or testing anything.

## Mechanism (verified from source, not assumed)

`G:\ComfyUI-Easy-Install\ComfyUI\comfy\cli_args.py`: `--lowvram`
explicitly does nothing if "dynamic VRAM" is enabled (per its own
`--help` text), and this install runs dynamic VRAM by default (log lines
throughout this project's testing show "Model X prepared for dynamic VRAM
loading... Staged"; `enables_dynamic_vram()` returns `True` unless
`--disable-dynamic-vram`/`--highvram`/`--gpu-only`/`--novram`/`--cpu` is
passed - none are). So `--lowvram` is a dead end on this install.

`--reserve-vram <float GB>` is the real lever. Default on this Windows box
with a 16GB+ card is already 700MB
(`model_management.py:800-808`: 600MB base on Windows + 100MB extra for
cards >15GB). Traced `load_models_gpu()`
(`model_management.py:936-949`): `lowvram_model_memory = max(0,
current_free_mem - minimum_memory_required, min(current_free_mem *
MIN_WEIGHT_MEMORY_RATIO, current_free_mem - minimum_inference_memory()))`,
where `minimum_inference_memory() = 0.8GB + extra_reserved_memory()` and
`extra_reserved_memory()` returns the (`--reserve-vram`-overridable)
reserved amount. A higher `--reserve-vram` directly shrinks the cap on how
much of a model can go fully resident, forcing more of it to stream from
CPU during inference instead - trading speed for VRAM headroom.

## Method

The batch launcher (`G:\ComfyUI-Easy-Install\Start ComfyUI.bat`) did not
forward its own arguments to `main.py` (no `%*`) - fixed with a one-line
addition (backup taken first:
`Start ComfyUI.bat.bak-2026-08-04`), user-approved before any restart.
User restarted ComfyUI with `"Start ComfyUI.bat" --reserve-vram 2.5`,
confirmed active via `/system_stats`'s `argv` field:
`["ComfyUI\\main.py", "--windows-standalone-build", "--output-directory",
"E:\\AI_Art", "--reserve-vram", "2.5"]`.

Per Codex's guidance, tested the hardest case first (the multi-reference
back-to-back scenario, since it had the worst prior margins - 196/463 MiB
in `RESULTS_RVrefchain.md`) rather than the easier single-image case.
Same method as that test: fresh `/free`, generate request, then
immediately (no `/free`) the 2-reference edit request. Fresh seeds
(`tests/router/runs/RVrefchain_reservevram_generate.graph.json`,
`RVrefchain_reservevram_edit.graph.json`). Log:
`vram_log_RVrefchain_reservevram.csv`.

## Result

**Worst sampled margin: 2410 MiB free - zero samples under 1000 MiB at
all**, compared to the original 196/463 MiB (n=2) without the flag. Log
confirms the predicted mechanism: `QwenImage`'s UNet now loads "partially;
9918.44 MB usable, 9857.12 MB loaded, **2881.92 MB offloaded**" instead of
"full load: True" - streaming ~2.9 GB from CPU during inference instead of
keeping it all resident. No errors, correct output produced (prompt_id
`70402a55-15fd-4cf8-9fe4-1f962d285e33`).

**Speed cost:** the edit request's wall time was 146.3s, vs.
`RESULTS_RVrefchain.md`'s load-to-next-load log window of ~92s for the
equivalent phase (not an exact apples-to-apples total-wall-time
comparison - that run's total prompt wall time wasn't separately
captured, only the log window between model-load lines) - order of
magnitude roughly 1.5-2x slower, a real and non-trivial cost, not free.

ComfyUI restored to its default launch (no `--reserve-vram`) immediately
after this test, per the user's explicit preference stated before the
experiment began.

## What this settles

- `--reserve-vram 2.5` is a validated mitigation for the worst tested
  back-to-back router scenario (multi-reference, no `/free`) - moves the
  worst-case margin from a project-record-tightest 196 MiB to a
  comfortable 2410 MiB, by design (forces partial UNet loading instead of
  full residency).
- The mechanism is understood and verified from source, not just observed
  empirically - this is a real, reproducible lever, not incidental
  variance.
- It trades full-load inference speed for headroom - not a free
  mitigation, a real tradeoff.

## What this does not settle / open concern

- n=1 - not a full performance benchmark, not repeated, and the
  single-image (easier) case was deliberately not re-tested this pass per
  Codex's guidance (the harder case passing comfortably was judged
  sufficient; skip further characterization unless a fuller benchmark
  table is wanted).
- No search for a smaller `--reserve-vram` value that might give "enough"
  margin at a lower speed cost - 2.5 was a first reasonable guess given
  the ~200 MiB-1 GiB range of prior tightest margins, not tuned.
- Not adopted as the default launch configuration - ComfyUI was restored
  to standard immediately after this test. Whether to permanently run
  with `--reserve-vram` (accepting the speed cost project-wide) versus
  keeping the existing `/free`-between-requests mandatory rule as the
  operational mitigation is an open choice, not decided by this test.
- Total prompt wall-time for the `--reserve-vram` run vs. baseline was not
  captured with fully matched methodology (see "Speed cost" above) - a
  precise before/after wall-time comparison at the same seeds would
  strengthen the cost estimate.
