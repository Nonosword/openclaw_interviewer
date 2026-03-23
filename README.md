# OpenClaw Interviewer Skill

一个按 OpenClaw 双 lane 规则组织的 AI 面试 skill。

目标只有两件事：
- 让 OpenClaw agent 能明确知道先执行什么
- 让所有执行命令都收敛到一个统一入口 `openclaw-interviewer`

另外增加一个机器友好的入口声明文件：
- `ENTRYPOINT.json`：命令真相文件，先告诉 agent 去哪里执行、Bootstrap 是什么、允许哪些命令前缀

## 1. 当前架构

项目由四层组成：
- `SKILL.md`：总入口，声明能力边界、Bootstrap 约束、命令映射、lane 边界
- `.agent/admin/*` 与 `.agent/candidate/*`：分别约束 admin 与 candidate lane
- `workflows/`：定义初始化与面试流程
- `interviewer/`：本地 capability、adapter、workflow、harness 实现

这不是一个只靠 prompt 猜命令的 skill，而是一个有明确执行入口的工程化 skill。

## 2. 目录结构

```text
openclaw_interviewer/
├── SKILL.md
├── README.md
├── config.yaml
├── setup
├── openclaw-interviewer
├── bin/                      # 兼容层，给本地实现用，不再作为 agent-facing 入口
├── .agent/
│   ├── admin/
│   └── candidate/
├── workflows/
├── .rag/
├── .workspace/
├── interviewer/
└── tests/
```

## 3. 统一命令入口

### 先定位 skill 根目录
agent 不应先猜命令，而应先找 skill 根目录。

唯一有效的 skill 根目录，必须同时包含：
- `SKILL.md`
- `ENTRYPOINT.json`
- `setup`
- `openclaw-interviewer`
- `config.yaml`

如果当前目录不同时包含这五个文件，就不是 skill 根目录，不应直接执行命令。

### Bootstrap 规则
首次进入当前项目根目录时，先运行：

```bash
./setup
```

`setup` 会做三件事：
- 检测并注册当前项目根目录的 `./openclaw-interviewer`
- 初始化默认配置
- 运行一次 `doctor` 并给出后续建议命令

### 后续规则
从 bootstrap 完成之后，所有命令一律写成：

```bash
openclaw-interviewer ...
```

不要再写：
- 绝对路径
- Python module 启动命令
- 旧的兼容入口

先读：
- `ENTRYPOINT.json`

## 4. Quick Start

### 第一步：Bootstrap

```bash
./setup
openclaw-interviewer doctor
```

### 第二步：进入对应 lane

管理员：

```bash
openclaw-interviewer admin candidate-list
```

候选人面试：

```bash
openclaw-interviewer interview identify --candidate-name 张三 --candidate-id C2026001
```

## 5. 双 Agent 设计

### 5.1 Candidate Agent

只面向候选人，负责：
- 身份核验
- 面试开始
- 提问
- 追问
- 案例题
- 收尾

允许的 lane：
- `openclaw.interview.*`

只允许的命令：
- `openclaw-interviewer interview identify`
- `openclaw-interviewer interview begin`
- `openclaw-interviewer interview status`
- `openclaw-interviewer interview next`
- `openclaw-interviewer interview reply`
- `openclaw-interviewer interview case-generate`
- `openclaw-interviewer interview finish`

禁止：
- `./setup`
- `openclaw-interviewer admin ...`
- `openclaw-interviewer doctor`
- `openclaw-interviewer harness ...`，除非明确进入测试场景

若统一入口不存在或失效，不允许猜绝对路径，不允许改用旧兼容入口，应要求 admin 先在项目根目录执行 `./setup`。

### 5.2 Admin Agent

只面向管理员/工作人员，负责：
- candidate list 管理
- 批量编辑/删除
- dialog + resume 添加 candidate
- 简历解析
- 岗位知识库与题库生成
- RAG 检查
- doctor / harness / 排障

允许的 lane：
- `openclaw.admin.*`

允许的命令：
- `./setup`，仅首次 bootstrap 或修复统一入口
- `openclaw-interviewer doctor`
- `openclaw-interviewer admin ...`
- `openclaw-interviewer harness ...`

禁止：
- 用 `openclaw-interviewer interview ...` 代替 candidate lane 承接真实候选人面试
- 向候选人暴露内部维护信息
- 缺少 `id / name / role / jd / scheduled / resume path` 时自行补全或创建占位文件

创建候选人前，admin agent 必须先拿到：
- `candidate_id`
- `candidate_name`
- `interview_role`
- `jd_id`，或者一份完整 JD 的 `jd_name / jd_role / jd_text`
- `scheduled_at`
- `resume_file` 的真实可读路径

如果缺任何一项，应继续询问管理员，而不是自己写 JD、自己创建空简历、再拿空文件去解析。

## 6. Admin lane 命令

### 6.1 查看 candidate list

```bash
openclaw-interviewer admin candidate-list
```

### 6.2 初始化所有候选人

```bash
openclaw-interviewer admin candidate-initialize
```

### 6.3 新增/更新 candidate

```bash
openclaw-interviewer admin candidate-upsert \
  --candidate-id C2026003 \
  --name 王五 \
  --role "Python后端工程师" \
  --jd-text "负责 Django 后端开发、接口设计、性能优化。" \
  --resume-file wangwu_resume.pdf \
  --scheduled-at 2026-03-25T15:00:00+08:00
```

成功创建后会自动执行该 candidate 的初始化链，写入：
- `jd_id`
- `question_bank_id`
- `resume_profile_file`
- `timer_id`
- `status=ready`

如果 JD 已经在库中，也可以直接关联：

```bash
openclaw-interviewer admin candidate-upsert \
  --candidate-id C2026003 \
  --name 王五 \
  --role "Python后端工程师" \
  --jd-id jd_python后端工程师 \
  --resume-file wangwu_resume.pdf \
  --scheduled-at 2026-03-25T15:00:00+08:00
```

### 6.4 用自然语言材料 + 简历添加 candidate

```bash
openclaw-interviewer admin candidate-add-from-dialog \
  --dialog-file ./candidate_dialog.txt \
  --resume-file zhaoliu_resume.pdf
```

### 6.5 批量更新 candidate

```bash
openclaw-interviewer admin candidate-bulk-update \
  --indices 1 2 3 4 5 \
  --scheduled-at 2026-03-30T14:00:00+08:00
```

```bash
openclaw-interviewer admin candidate-bulk-update \
  --indices 1 2 3 4 5 \
  --enable false
```

### 6.6 批量删除 candidate

```bash
openclaw-interviewer admin candidate-bulk-remove --indices 1 2 3
```

### 6.7 删除单个 candidate

```bash
openclaw-interviewer admin candidate-remove --candidate-id C2026003
```

### 6.8 刷新单个 candidate

```bash
openclaw-interviewer admin candidate-refresh --candidate-id C2026003
```

### 6.9 解析简历

```bash
openclaw-interviewer admin resume-parse \
  --resume-file wangwu_resume.pdf \
  --role "Python后端工程师" \
  --jd-id jd_python后端工程师 \
  --candidate-name 张三
```

### 6.10 生成岗位知识库

```bash
openclaw-interviewer admin domain-generate \
  --jd-id jd_python后端工程师
```

### 6.10.1 维护 JD 库

```bash
openclaw-interviewer admin jd-list
```

```bash
openclaw-interviewer admin jd-upsert \
  --jd-role "Python后端工程师" \
  --jd-text "负责 Django 后端开发、接口设计、性能优化。"
```

### 6.11 检查 config / capabilities / retrieval

```bash
openclaw-interviewer admin config-show
openclaw-interviewer admin capabilities-list
openclaw-interviewer admin retrieval-inspect
```

## 7. Candidate lane 命令

### 7.1 识别候选人

```bash
openclaw-interviewer interview identify \
  --candidate-name 张三 \
  --candidate-id C2026001
```

### 7.2 开始面试

```bash
openclaw-interviewer interview begin --session-id <session>
```

### 7.3 查看状态

```bash
openclaw-interviewer interview status --session-id <session>
```

### 7.4 获取下一题

```bash
openclaw-interviewer interview next --session-id <session>
```

### 7.5 提交回答

```bash
openclaw-interviewer interview reply \
  --session-id <session> \
  --candidate-message "首先我会确认背景、目标和约束，然后通过日志、监控、指标、回滚和压测来分析问题。"
```

### 7.6 生成案例题

```bash
openclaw-interviewer interview case-generate --session-id <session>
```

### 7.7 结束面试

```bash
openclaw-interviewer interview finish --session-id <session>
```

## 8. 测试与排障

### 健康检查

```bash
openclaw-interviewer doctor
```

### Harness

```bash
openclaw-interviewer harness --scenario full_interview
openclaw-interviewer harness --scenario admin_ops
openclaw-interviewer harness --scenario security_probe
```

### 单测

```bash
python3 -m unittest discover -s tests -v
```

## 9. 关键规则

- 首次 bootstrap 只能用 `./setup`
- bootstrap 完成后，所有 skill 命令只写 `openclaw-interviewer ...`
- candidate lane 不进入 admin lane
- admin lane 不代替 live candidate lane
- 入口不存在时先修复 `./setup`，不要猜路径
- 当前目录不是 skill 根目录时，先切到包含 `ENTRYPOINT.json` 的目录，再执行命令
- 不向候选人暴露内部评分、trace、题库和配置
- 原始简历文件放在 `.rag/resume/`
- 简历衍生产物 `extract/profile/questions` 放在 `.rag/resume/data/`
