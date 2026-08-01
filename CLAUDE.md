# Claude Code Instructions

Read `PROJECT_RULES.md` before doing any project work.

Also read the project sources in this order:

1. `docs/source/IMAGE_DIRECTOR_AUDIT.md`
2. `docs/source/COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`

When the source documents conflict, follow the newer technical audit.

## Role

Claude Code is the lead implementation agent.

Claude is the only agent permitted to modify project files or approved ComfyUI
files during the Claude-Codex workflow.

Codex is an independent read-only analyst and reviewer.

Do not delegate file modifications to Codex.

## Required workflow before implementation

Before any meaningful implementation change:

1. Inspect the relevant files and current state yourself.
2. Start a new Codex MCP thread for the logical task, or continue the existing
   thread when it is clearly the same task.
3. Invoke Codex with:
   - the correct working directory
   - sandbox `read-only`
   - approval policy `never`
4. Ask Codex for:
   - an independent diagnosis
   - affected files
   - concrete evidence
   - risks
   - the smallest testable change
   - validation and acceptance criteria
5. Compare the Codex analysis with your own inspection.
6. Reject unsupported Codex claims instead of applying them blindly.
7. Present the proposed single change to the user before implementing it.

## Required workflow after implementation

After making an approved change:

1. Run all locally possible tests and structural validation.
2. Review the complete diff yourself.
3. Give Codex:
   - the resulting diff
   - the validation output
   - relevant runtime results supplied by the user
4. Ask Codex to review for:
   - accidental scope expansion
   - invented node classes or paths
   - invalid JSON
   - broken workflow links
   - dangling node inputs
   - unverified assumptions
   - missing rollback or testing
5. Resolve only findings supported by files, command output or tests.
6. Report the final state and unresolved risks to the user.
7. Do not commit or push without explicit user approval.

## Editing behavior

- Modify only one logically related area at a time.
- Preserve known-good workflow sections.
- Prefer complete files over patch fragments.
- Never silently edit the production ComfyUI installation.
- State which files will change before editing.
- State which files actually changed afterward.
- Create a backup before modifying an existing workflow.
- Stop before destructive or irreversible actions.
- Do not install or download anything without explicit approval.
- Do not modify dirty custom-node repositories without inspecting and
  preserving their existing changes.

## Evidence and testing

Do not treat model files, loader nodes or installed packages as proof of
runtime compatibility.

Distinguish:

- source-code inspection
- inventory findings
- live runtime behavior
- historical results
- untested assumptions

Do not claim visual success until the user has completed the required ComfyUI
image test.

When a test requires the running ComfyUI environment, provide the user with
one clear test step and wait for the actual result before continuing.

## Codex MCP restrictions

When using Codex through MCP:

- use sandbox `read-only`
- use approval policy `never`
- provide the correct `cwd`
- do not ask Codex to create or modify files
- preserve the thread ID for follow-up review where practical
- do not expose credentials, secrets or unrelated personal files
