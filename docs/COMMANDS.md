# COMMANDS

Explicit executable command map for the OpenClaw Interviewer skill.

## Rule
- Read `ENTRYPOINT.json` first
- The skill root must contain `SKILL.md`, `ENTRYPOINT.json`, `setup`, `openclaw-interviewer`, and `config.yaml`
- If the current directory does not contain all five markers, do not run commands there
- First bootstrap in the current project root: `./setup`
- After bootstrap, write commands only as `openclaw-interviewer ...`
- Do not write absolute paths
- Do not write Python module launch commands
- Do not expose legacy wrapper scripts as agent-facing commands
- If candidate creation fields are incomplete, ask follow-up questions instead of inventing JD or resume files
- Do not create temporary JD files in the skill directory to fill missing input; use an existing admin-provided `--jd-file` or pass direct JD text with `--jd-text` / `--jd`

## Bootstrap
- `./setup`
- `openclaw-interviewer doctor`
- `./setup` uses `uv venv .venv`, registers `openclaw-interviewer` and `openclaw-interviewer-admin`, and syncs `.agent/*.md` into their workspaces

## Admin lane
- `openclaw-interviewer admin config-show`
- `openclaw-interviewer admin capabilities-list`
- `openclaw-interviewer admin candidate-list`
- `openclaw-interviewer admin candidate-initialize`
- `openclaw-interviewer admin candidate-upsert ...`
- `openclaw-interviewer admin candidate-add-from-dialog --dialog-file <path> --resume-file <file> ...`
- `openclaw-interviewer admin candidate-bulk-update ...`
- `openclaw-interviewer admin candidate-bulk-remove ...`
- `openclaw-interviewer admin candidate-remove ...`
- `openclaw-interviewer admin candidate-refresh ...`
- `openclaw-interviewer admin resume-parse ...`
- `openclaw-interviewer admin domain-generate ...`
- `openclaw-interviewer admin retrieval-inspect`

## Candidate lane
- `openclaw-interviewer interview identify ...`
- `openclaw-interviewer interview begin ...`
- `openclaw-interviewer interview status ...`
- `openclaw-interviewer interview next ...`
- `openclaw-interviewer interview reply ...`
- `openclaw-interviewer interview case-generate ...`
- `openclaw-interviewer interview finish ...`

## Testing
- `openclaw-interviewer doctor`
- `openclaw-interviewer harness --scenario identify_only`
- `openclaw-interviewer harness --scenario full_interview`
- `openclaw-interviewer harness --scenario security_probe`
- `openclaw-interviewer harness --scenario transcript_replay --transcript-file <path>`
- `openclaw-interviewer harness --scenario admin_ops`
