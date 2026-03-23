# ENDPOINTS

本文档列出当前 adapter 已实现的 endpoint、主要输入和典型用途。

## Route use boundary
- `candidate` agent 只能使用 `openclaw.interview.*`
- `admin` agent 只能使用 `openclaw.admin.*`
- `admin` 在 harness/replay 场景中可以观测 interview flow，但不应替代 live candidate lane


## Admin endpoints

### `openclaw.admin.config.show`
返回当前 `config.yaml` 解析结果。

### `openclaw.admin.capabilities.list`
返回 capability 注册表。

### `openclaw.admin.domain.ensure`
输入：
- `jd_id`
- `jd_role` 可选
- `jd_text` 可选

作用：
- 若岗位知识库或题库不存在则生成
- 若已存在则只返回引用

### `openclaw.admin.domain.generate`
输入同上。

作用：
- 强制生成领域知识与岗位题库

### `openclaw.admin.resume.parse`
输入：
- `resume_file`
- `role_name`
- `jd_text`
- `candidate_name` 可选

作用：
- 解析 PDF / txt
- 生成 `.rag/resume/data/*.profile.json`
- 生成 `.rag/resume/data/*.questions.jsonl`
- 若 PDF 解析失败，会返回结构化错误信息（含尝试过的解析引擎和管理员后续动作建议）

### `openclaw.admin.jd.list`
返回 JD 注册表。

### `openclaw.admin.jd.upsert`
输入：
- `jd_id` 可选
- `jd_name`
- `jd_role`
- `jd_text`

作用：
- 创建或更新 `.rag/jd/jd.jsonl`
- 为 candidate/domain 提供稳定的 JD 引用

### `openclaw.admin.candidate.initialize`
无输入。

作用：
- 初始化所有启用中的 candidate
- 会写入岗位知识、简历 profile、简历题库、timer 等衍生数据

### `openclaw.admin.timer.ensure`
输入：
- `candidate_id`
- `scheduled_at`

### `openclaw.admin.candidate.list`
返回候选人列表，附带稳定 `index`。

### `openclaw.admin.candidate.upsert`
输入典型字段：
- `candidate_id`
- `candidate_name`
- `interview_role`
- `jd_id` 或 `jd_name + jd_role + jd_text`
- `resume_file`
- `scheduled_at`
- `enabled`

作用：
- 写入或更新 candidate 主记录
- 若 candidate 可用，则自动执行该 candidate 的初始化链并把状态推进到 `ready`
- 若自动初始化中的简历解析失败，则返回 `initialization_error`，并保留 candidate 记录供后续 `candidate-refresh`

### `openclaw.admin.candidate.add_from_dialog`
输入：
- `dialog_text`
- `resume_file`
- `candidate_id` 可选

作用：
- 由 OpenClaw subagent worker 调用 models 从自然语言文本中解析 candidate 信息并新增
- 成功新增后自动执行初始化链
- 若初始化失败，同样返回 `initialization_error`

### `openclaw.admin.candidate.bulk_update`
输入：
- `candidate_ids` 可选
- `indices` 可选
- `updates`

常见 `updates`：
- `enabled`
- `scheduled_at`

### `openclaw.admin.candidate.bulk_remove`
输入：
- `candidate_ids` 或 `indices`

### `openclaw.admin.candidate.remove`
输入：
- `candidate_id`

### `openclaw.admin.candidate.refresh`
输入：
- `candidate_id`

作用：
- 重新执行该 candidate 的初始化链

### `openclaw.admin.retrieval.inspect`
返回 `.rag` / retrieval 基本状态。

---

## Interview endpoints

### `openclaw.interview.identify`
输入：
- `candidate_name`
- `candidate_id`
- `session_id` 可选

无 name/id 时会进入等待身份输入状态。

### `openclaw.interview.begin`
输入：
- `session_id`

作用：
- 创建初始队列
- 标记面试开始

### `openclaw.interview.status`
输入：
- `session_id`

返回：
- 当前 state
- `current_question_id`
- pending 数量
- followup 计数

### `openclaw.interview.next`
输入：
- `session_id`

作用：
- 获取下一题
- 必要时自动切到 case 或 finish

### `openclaw.interview.reply`
输入：
- `session_id`
- `candidate_message`

作用：
- 探测越权请求
- 评分
- 追问或进入下一题

### `openclaw.interview.case_generate`
输入：
- `session_id`

作用：
- 直接触发综合案例题

### `openclaw.interview.finish`
输入：
- `session_id`

作用：
- 聚合最终结果并落库
