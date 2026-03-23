# HEARTBEAT.md

管理员侧 heartbeat 用于周期性运维检查。

## 检查项
- candidate.jsonl 是否有未初始化项
- resume/domain/question bank 衍生文件是否缺失
- runtime/interview/score 是否出现异常记录
- retrieval manifest 是否异常
- harness/tests 最近是否失败

## 输出要求
- 列出问题
- 标明影响范围
- 给出下一步建议
