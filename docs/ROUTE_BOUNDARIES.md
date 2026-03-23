# ROUTE BOUNDARIES

This skill uses one `SKILL.md` with two separate lanes and one unified command entry.

## Candidate lane
### Allowed routes
- `openclaw.interview.identify`
- `openclaw.interview.begin`
- `openclaw.interview.status`
- `openclaw.interview.next`
- `openclaw.interview.reply`
- `openclaw.interview.case_generate`
- `openclaw.interview.finish`

### Allowed commands
- `openclaw-interviewer interview identify ...`
- `openclaw-interviewer interview begin ...`
- `openclaw-interviewer interview status ...`
- `openclaw-interviewer interview next ...`
- `openclaw-interviewer interview reply ...`
- `openclaw-interviewer interview case-generate ...`
- `openclaw-interviewer interview finish ...`

### Forbidden routes
- any `openclaw.admin.*`

### Forbidden commands
- `./setup`
- `openclaw-interviewer admin ...`
- `openclaw-interviewer doctor`
- `openclaw-interviewer harness ...` except explicit test mode
- any legacy compatibility wrapper for candidate execution

## Admin lane
### Allowed routes
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

### Allowed commands
- `./setup` only for bootstrap or entry repair
- `openclaw-interviewer doctor`
- `openclaw-interviewer admin ...`
- `openclaw-interviewer harness ...`

### Forbidden routes
- live candidate interview routes for real candidate handling

### Forbidden commands
- using `openclaw-interviewer interview ...` as a substitute for the candidate lane during live interview
