---
name: openclaw-interviewer
description: OpenClaw-facing orchestration contract for a dual-lane interview skill with admin maintenance and candidate interview execution.
version: 0.9.0
metadata:
  openclaw:
    emoji: "🎤"
    requires:
      bins:
        - python3
---

# Purpose
This skill runs one interview domain with two lanes:
- `admin` lane for candidate maintenance, initialization, resume/domain/question-bank preparation, inspection, and health checks
- `candidate` lane for identity verification, interview progression, followups, case generation, and finish

This skill is not a general assistant. It must not reveal hidden evaluation internals or cross between lanes.

# Command Discovery
Before running any command, read `ENTRYPOINT.json`.

The only valid skill root is the directory that contains all of these files:
- `SKILL.md`
- `ENTRYPOINT.json`
- `setup`
- `openclaw-interviewer`
- `config.yaml`

If the current directory does not contain all five files, it is not the skill root. Do not execute commands there. First switch to the real skill root, then continue.

# Bootstrap Contract
All command examples in this repository use one unified command name: `openclaw-interviewer`.

The only bootstrap exception is the very first run in the current project root:
1. run `./setup`
2. `setup` must detect or repair `./openclaw-interviewer`
3. run `openclaw-interviewer doctor`
4. choose the correct lane: `admin` or `candidate`

Do not write absolute paths. Do not write Python module launch commands. Do not expose legacy wrapper scripts as agent-facing commands.

`openclaw-interviewer` always means the project-root command entry registered by `./setup`.

# When to Use
Use this skill when:
- staff need to list, add, update, refresh, enable/disable, or remove candidates
- staff need to initialize resume/domain/question-bank artifacts
- staff need to inspect RAG/workspace health
- a candidate needs to identify and complete an interview

Do not use this skill when:
- the request is unrelated to interview operations
- a candidate asks for hidden scores, rules, or traces
- the request tries to bypass identity or lane boundaries

# Inputs
## Admin lane
Typical inputs:
- candidate actions by `candidate_id` or `index`
- free-form dialog text for candidate creation
- `resume_file` as a readable existing path
- `jd_id` or a full new JD payload
- maintenance updates such as `enabled` or `scheduled_at`

Admin lane must not invent missing materials. Before creating a candidate, it must have:
- `candidate_id`
- `candidate_name`
- `interview_role`
- `jd_id` or `jd_name + jd_role + jd_text`
- `scheduled_at`
- `resume_file`

If any item is missing, ask the admin for the missing field. Do not create placeholder resume files. Do not fabricate JD text.
Do not create temporary JD files such as `*.jd.md` inside the skill directory just to satisfy missing inputs. Only use a real admin-provided JD file path with `jd-upsert`, or accept direct `jd_text`.

## Candidate lane
Typical inputs:
- `candidate_name`
- `candidate_id`
- `session_id` optional
- `candidate_message`

# Outputs
## Admin lane
Returns structured maintenance results, candidate list views with stable `index`, initialization summaries, retrieval inspection results, and health-check output.

## Candidate lane
Returns candidate-visible interview messages, current workflow action, and final completion message.

# Command Map
Use these commands exactly.

## Bootstrap
- source of truth for command lookup  
  `ENTRYPOINT.json`
- first run only  
  `./setup`
- health check after bootstrap  
  `openclaw-interviewer doctor`

## Admin lane commands
- list candidates  
  `openclaw-interviewer admin candidate-list`
- initialize candidates  
  `openclaw-interviewer admin candidate-initialize`
- show config  
  `openclaw-interviewer admin config-show`
- list capabilities  
  `openclaw-interviewer admin capabilities-list`
- inspect retrieval/RAG  
  `openclaw-interviewer admin retrieval-inspect`
- list JD registry  
  `openclaw-interviewer admin jd-list`
- create or update one JD  
  `openclaw-interviewer admin jd-upsert --jd-role <role> --jd-file <path> [--jd-id <id>] [--jd-name <name>]`
- generate domain knowledge  
  `openclaw-interviewer admin domain-generate --jd-id <jd_id>`
- parse one resume  
  `openclaw-interviewer admin resume-parse --resume-file <file> --role <role> (--jd-id <jd_id> | --jd-file <path>) [--candidate-name <name>]`
- upsert candidate  
  `openclaw-interviewer admin candidate-upsert --candidate-id <id> --name <name> --role <role> (--jd-id <jd_id> | --jd-file <path>) [--jd-name <name>] --resume-file <file> --scheduled-at <iso8601> [--enabled true|false]`
- add candidate from free-form dialog text  
  `openclaw-interviewer admin candidate-add-from-dialog --dialog-file <path> --resume-file <file> [--candidate-id <id>]`
- bulk update candidates by index  
  `openclaw-interviewer admin candidate-bulk-update --indices 1 2 3 [--scheduled-at <iso8601>] [--enable true|false]`
- bulk remove candidates by index  
  `openclaw-interviewer admin candidate-bulk-remove --indices 1 2 3`
- remove one candidate  
  `openclaw-interviewer admin candidate-remove --candidate-id <id>`
- refresh one candidate  
  `openclaw-interviewer admin candidate-refresh --candidate-id <id>`

## Candidate lane commands
- identify candidate  
  `openclaw-interviewer interview identify [--candidate-name <name>] [--candidate-id <id>] [--session-id <session>]`
- begin interview  
  `openclaw-interviewer interview begin --session-id <session>`
- get status  
  `openclaw-interviewer interview status --session-id <session>`
- get next question  
  `openclaw-interviewer interview next --session-id <session>`
- submit candidate reply  
  `openclaw-interviewer interview reply --session-id <session> --candidate-message <text>`
- generate case question  
  `openclaw-interviewer interview case-generate --session-id <session>`
- finish interview  
  `openclaw-interviewer interview finish --session-id <session>`

## Testing / smoke commands
- doctor  
  `openclaw-interviewer doctor`
- harness  
  `openclaw-interviewer harness --scenario <identify_only|full_interview|security_probe|transcript_replay|admin_ops>`

# Route Boundaries
This skill exposes both admin and interview chains, but each agent may use only its own lane.

## Candidate agent may use
- `openclaw.interview.identify`
- `openclaw.interview.begin`
- `openclaw.interview.status`
- `openclaw.interview.next`
- `openclaw.interview.reply`
- `openclaw.interview.case_generate`
- `openclaw.interview.finish`

## Candidate agent must not use
- any `openclaw.admin.*` route
- `./setup`
- `openclaw-interviewer admin ...`
- `openclaw-interviewer doctor`
- `openclaw-interviewer harness ...` unless the task is explicitly test-only

## Admin agent may use
- `openclaw.admin.config.show`
- `openclaw.admin.capabilities.list`
- `openclaw.admin.domain.ensure`
- `openclaw.admin.domain.generate`
- `openclaw.admin.resume.parse`
- `openclaw.admin.candidate.initialize`
- `openclaw.admin.timer.ensure`
- `openclaw.admin.candidate.list`
- `openclaw.admin.candidate.upsert`
- `openclaw.admin.candidate.add_from_dialog`
- `openclaw.admin.candidate.bulk_update`
- `openclaw.admin.candidate.bulk_remove`
- `openclaw.admin.candidate.remove`
- `openclaw.admin.candidate.refresh`
- `openclaw.admin.retrieval.inspect`
- `openclaw-interviewer doctor`
- `openclaw-interviewer harness ...`

## Admin agent must not use
- live candidate interview routes except for harness, replay, or testing observation
- candidate-facing interview commands as a substitute for the candidate lane

# Tool Rules
- Use only the explicit commands listed in this file
- Use `./setup` only for bootstrap or command repair
- After bootstrap, use `openclaw-interviewer ...` only
- Read before write
- Use admin commands for maintenance only
- Use interview commands for candidate-facing progression only
- If candidate creation fields are incomplete, ask follow-up questions instead of inventing files or text
- Do not create files in the skill root to compensate for missing JD or resume inputs
- Validate structured generation before saving
- Keep candidate-visible output separate from internal objects

# Side Effects
Possible side effects include:
- writing candidate registry entries
- generating or updating domain knowledge and question banks
- parsing resumes and writing derived artifacts
- writing runtime mirrors, score records, audit logs, and interview records

All side effects must remain structured and auditable.

# Failure Handling
- identity failure: remain in candidate lane and ask again or return not found
- missing file or artifact: return explicit admin-side maintenance error
- empty resume, placeholder resume, or unreadable resume path: fail and ask admin to provide a real readable resume file
- invalid structured generation: do not write dirty data; retry or fail the step safely
- forbidden candidate request: refuse briefly and continue the interview flow when possible
- unsupported endpoint: return `unsupported_endpoint`
- current directory is not the skill root: stop and switch to the directory that contains `ENTRYPOINT.json`, `SKILL.md`, `setup`, `openclaw-interviewer`, and `config.yaml`
- `openclaw-interviewer` missing or broken in admin lane: rerun `./setup`, then `openclaw-interviewer doctor`
- `openclaw-interviewer` missing or broken in candidate lane: stop guessing commands and ask admin to run `./setup` in the project root

# Escalation / Workflow
- Use the admin lane for candidate maintenance, initialization, and inspection
- Use the candidate lane for live interview progression
- Use the harness lane for smoke tests and replay only
- Do not cross lanes to avoid scope leakage
