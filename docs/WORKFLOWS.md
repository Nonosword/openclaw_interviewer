# WORKFLOWS

当前项目采用 Lobster 风格 workflow 声明文件，并由本地 workflow runner 执行。

## 1. `candidate_init.lobster.yaml`
表示 candidate 初始化流程：
- 读取 candidate
- 确保知识库
- 解析简历
- 生成题库
- 建 timer
- 标记 ready

实际入口：
- `openclaw.admin.candidate.initialize`
- `openclaw.admin.candidate.refresh`

## 2. `admin_ops.lobster.yaml`
表示管理员维护流程：
- list candidates
- add_from_dialog
- bulk_update
- bulk_remove
- refresh_candidate
- inspect_rag

实际入口：
- `openclaw.admin.candidate.list`
- `openclaw.admin.candidate.add_from_dialog`
- `openclaw.admin.candidate.bulk_update`
- `openclaw.admin.candidate.bulk_remove`
- `openclaw.admin.candidate.refresh`
- `openclaw.admin.retrieval.inspect`

## 3. `interview_start.lobster.yaml`
表示候选人识别成功后，面试开始与初始队列构建。

实际入口：
- `openclaw.interview.identify`
- `openclaw.interview.begin`

## 4. `interview_round.lobster.yaml`
表示单轮问答：
- 取题
- 提问
- 收回答
- 评分
- 决策追问
- 切下一题

实际入口：
- `openclaw.interview.next`
- `openclaw.interview.reply`

## 5. `interview_case.lobster.yaml`
表示常规队列完成后的综合案例题生成与提问。

实际入口：
- `openclaw.interview.case_generate`
- `openclaw.interview.next` 自动触发

## 6. `interview_finalize.lobster.yaml`
表示最终汇总与记录写入。

实际入口：
- `openclaw.interview.finish`
- `openclaw.interview.next` 自动收束
