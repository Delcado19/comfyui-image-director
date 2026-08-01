# ComfyUI Image Director — Project Rules

## Source priority

Read the project sources in this order:

1. `docs/source/IMAGE_DIRECTOR_AUDIT.md`
2. `docs/source/COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`

When the documents conflict, the newer technical audit has priority.

Do not silently combine contradictory claims. Identify the conflict and use the
newer verified finding unless newer runtime evidence supersedes it.

## Project goal

Build a modular local Image Director for ComfyUI that converts natural-language
instructions and reference images into a structured plan and routes the task to
an appropriate generation or editing workflow.

Version 1 must remain small, inspectable, reproducible and reversible.

## Production environment

ComfyUI root:

`G:\ComfyUI-Easy-Install\ComfyUI`

Separate development repository:

`C:\Users\Delcado\Documents\Software_Projects\comfyui-image-director`

The ComfyUI installation is a customized working environment.

Do not reorganize its existing folder structure.

## Collaboration model

Claude and Codex are equal technical reasoning partners.

Both agents must:

- inspect the available evidence independently
- develop their own diagnosis and solution proposal
- identify assumptions, risks and missing evidence
- compare competing approaches
- challenge unsupported conclusions
- refine the solution through discussion
- distinguish consensus from unresolved disagreement

Neither agent should be treated as an unquestioned authority.

Claude coordinates the interaction because the user communicates through
Claude Code, but Claude must not reduce Codex to a one-way advisor or a final
rubber-stamp reviewer.

Codex must be given enough context to reason independently.

Claude should use follow-up calls in the same Codex MCP thread to discuss:

- differences between both analyses
- objections to proposed solutions
- alternative implementations
- evidence supporting each option
- testability and rollback
- unresolved technical uncertainty

The goal is a reasoned joint conclusion, not automatic agreement.

## Decision process

Before a meaningful implementation decision:

1. Claude inspects the relevant files and forms an initial analysis.
2. Codex independently inspects the same problem in read-only mode.
3. Claude compares both analyses.
4. Claude sends material differences, objections or open questions back to
   Codex using the same MCP thread.
5. Claude and Codex refine the options until:
   - they reach a supported consensus, or
   - the remaining disagreement is clearly documented.
6. Claude presents the resulting recommendation to the user, including:
   - the preferred solution
   - meaningful alternatives
   - supporting evidence
   - remaining disagreement
   - risks and required tests
7. The user approves consequential implementation changes.
8. Claude performs approved file modifications.

A disagreement must not be hidden merely to present a single answer.

When evidence cannot decide between alternatives, prefer a controlled test over
speculation.

## File modification authority

Claude Code is the only agent permitted to modify:

- files in the development repository
- approved ComfyUI workflow files
- approved ComfyUI configuration or code

Codex remains read-only when invoked through Claude Code.

This restriction concerns file operations only. It does not make Codex
subordinate in architectural or technical decision-making.

Codex may propose concrete changes, algorithms, structures and complete
solutions, but Claude must evaluate and implement them.

## Current architecture status

The intended minimal architecture is:

1. Instruction and source/reference images
2. Standalone image analyzer
3. Structured JSON edit plan
4. Generation or editing branch

Current candidate execution branches:

- Generation: Z-Image Turbo
- Image editing: Qwen Image Edit 2509
- Qwen Image Edit 2511: future A/B candidate
- FLUX.2: outside the Version-1 critical path until separately measured

The standalone analyzer implementation is unresolved.

Do not assume that the installed Qwen2.5-VL files used by Qwen Image Edit can
also be loaded directly as an independent analyzer.

The current audit states that analyzer-only Test A and combined Test C were
blocked pending a valid Layer-A analyzer decision.

## Mandatory safety rules

- Do not modify ComfyUI files unless the current user-approved task requires it.
- Do not install or download models, nodes or dependencies without explicit
  user approval.
- Do not pull, reset, rebase, clean or overwrite dirty custom-node repositories.
- Do not invent node classes, model paths, ports, APIs or command-line options.
- Verify installed node classes and concrete model paths before using them.
- Preserve existing working workflow sections.
- Create a backup before modifying an existing workflow.
- Validate complete workflow JSON after every workflow edit.
- Restart ComfyUI after installing or changing custom-node code before judging
  a workflow created in the GUI.
- Do not change global ComfyUI configuration unless strictly necessary and
  explicitly approved.
- Do not create commits or push changes without explicit user approval.

## Development method

Work in small, testable steps.

For every implementation step:

1. Inspect the relevant files and current state.
2. Complete the joint Claude-Codex decision process.
3. State the exact scope of the proposed change.
4. Identify files that would be modified.
5. Explain the expected result and the test.
6. Obtain user approval where required.
7. Let Claude change only one logically related part.
8. Run all locally possible validation.
9. Request the user's real ComfyUI runtime test when local validation is not
   sufficient.
10. Let Claude and Codex jointly evaluate the resulting evidence.
11. Review the complete diff.
12. Record unresolved risks honestly.

Do not bundle unrelated fixes.

## Evidence rules

Distinguish clearly between:

- verified installation facts
- findings from source-code inspection
- live runtime test results
- historical results from older hardware
- assumptions requiring a new test
- conclusions agreed by both agents
- unresolved disagreement between the agents

File or node presence is not proof of runtime compatibility.

Disk size is not proof of simultaneous VRAM usage.

Do not claim visual quality, identity preservation or edit locality without an
actual controlled image test.

Consensus between Claude and Codex is not evidence by itself. Their conclusion
must remain grounded in files, source code, logs, documentation or tests.

## Workflow requirements

- Prefer existing native ComfyUI nodes and already-installed custom nodes.
- Use only confirmed node classes.
- Provide complete workflow JSON files rather than isolated patch fragments.
- Keep model loading and text-encoder loading separately switchable where the
  workflow requires it.
- Keep GGUF and safetensors loader paths separate.
- Do not add fallback paths for SageAttention unless the user explicitly asks.
- Expose routing decisions and the structured edit plan visibly.
- Preserve sufficient metadata for reproducibility.
- Do not make the router a black box.

## Testing requirements

Use controlled A/B tests.

Keep all unrelated variables constant and change only one variable at a time.

Relevant evaluation categories include:

- identity preservation
- instruction compliance
- edit locality
- non-target preservation
- material realism
- lighting consistency
- anatomy
- background preservation
- VRAM behavior
- execution time
- reproducibility

When Claude and Codex prefer different technically plausible solutions, design
the smallest controlled comparison that can resolve the disagreement.

## Communication

Normal discussion may be in German.

Technical project documentation and persistent project files should be written
in English unless the user explicitly requests otherwise.

Prefer complete copy-and-paste-ready files and commands.

Report failures and uncertainty directly. Do not hide incomplete validation,
agent disagreement or unsupported assumptions.
