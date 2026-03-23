# OPERATIONS

本文档面向管理员，说明日常维护与推荐操作顺序。

## 0. Bootstrap
首次进入当前项目根目录时：

```bash
./setup
openclaw-interviewer doctor
```

之后所有 skill 操作都统一写成 `openclaw-interviewer ...`。
`./setup` 会同时创建项目 `.venv`、注册 `openclaw-interviewer` / `openclaw-interviewer-admin` 两个 agent，并同步 `.agent/*.md` 到各自 workspace。

## 0.1 创建候选人的硬约束
执行新增前必须已经拿到：
- `candidate_id`
- `candidate_name`
- `interview_role`
- `jd_id`，或者 `jd_name / jd_role / jd_text`
- `scheduled_at`
- `resume_file` 的真实可读路径

如果缺任何一项，继续向管理员追问。不要自行创建空简历、占位简历或虚构 JD。
也不要为了补齐参数，在当前 skill 目录里新建临时 `*.jd.md` 文件；只有管理员明确提供真实 `jd_file` 路径时才使用文件方式。

## 1. 每日基础检查
```bash
openclaw-interviewer admin capabilities-list
openclaw-interviewer admin retrieval-inspect
openclaw-interviewer admin candidate-list
```

## 2. 新增 candidate
### 方法 0：先维护 JD 库
```bash
openclaw-interviewer admin jd-list
```

```bash
openclaw-interviewer admin jd-upsert \
  --jd-role "Python后端工程师" \
  --jd-text "负责 Django 后端开发、接口设计、性能优化。"
```

### 方法 A：结构化新增
```bash
openclaw-interviewer admin candidate-upsert \
  --candidate-id C2026008 \
  --name 赵六 \
  --role "Python后端工程师" \
  --jd-text "负责 Django 后端开发、接口设计、性能优化。" \
  --resume-file zhaoliu_resume.pdf \
  --scheduled-at 2026-04-06T14:00:00+08:00
```

### 方法 B：对话式新增
```bash
openclaw-interviewer admin candidate-add-from-dialog \
  --dialog-file ./candidate_dialog.txt \
  --resume-file zhaoliu_resume.pdf
```

## 3. 刷新 candidate
当以下内容变更时建议刷新：
- resume PDF
- JD
- 岗位
- 需要重建知识库/题库

```bash
openclaw-interviewer admin candidate-refresh --candidate-id C2026008
```

## 4. 批量改面试时间或启用状态
先看列表中的 `index`，再执行：

```bash
openclaw-interviewer admin candidate-bulk-update \
  --indices 1 2 3 \
  --scheduled-at 2026-04-07T09:00:00+08:00 \
  --enable true
```

## 5. 批量删除
```bash
openclaw-interviewer admin candidate-bulk-remove --indices 7 8
```

## 6. 初始化全部启用候选人
```bash
openclaw-interviewer admin candidate-initialize
```

说明：
- `candidate-upsert` 和 `candidate-add-from-dialog` 成功后已经会自动初始化对应 candidate
- 如果自动初始化中的简历解析失败，返回结果会包含 `initialization_error`；此时 candidate 记录会保留，管理员可重新上传简历后执行 `openclaw-interviewer admin candidate-refresh --candidate-id <id>`
- 这个命令主要用于批量补跑或重建

## 7. 推荐的发布前检查
```bash
openclaw-interviewer harness --scenario admin_ops
openclaw-interviewer harness --scenario full_interview
openclaw-interviewer harness --scenario security_probe
```
