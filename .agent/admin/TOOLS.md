# TOOLS.md

管理员侧使用维护、检查与测试相关命令。

## 统一命令入口
- 首次 bootstrap 或修复入口时：`./setup`
- 其余所有场景：`openclaw-interviewer ...`

## 命令列表
- 检查健康状态  
  `openclaw-interviewer doctor`
- 查看 config  
  `openclaw-interviewer admin config-show`
- 查看 capabilities  
  `openclaw-interviewer admin capabilities-list`
- 查看 candidate list  
  `openclaw-interviewer admin candidate-list`
- 查看 JD 库  
  `openclaw-interviewer admin jd-list`
- 新增/更新 JD  
  `openclaw-interviewer admin jd-upsert --jd-role <role> --jd-file <path> [--jd-id <id>] [--jd-name <name>]`
- 初始化 candidates  
  `openclaw-interviewer admin candidate-initialize`
- 从 dialog 添加 candidate  
  `openclaw-interviewer admin candidate-add-from-dialog --dialog-file <path> [--resume-file <file>]`
- 新增/更新 candidate  
  `openclaw-interviewer admin candidate-upsert ...`
- 批量更新 candidate  
  `openclaw-interviewer admin candidate-bulk-update --indices ...`
- 批量删除 candidate  
  `openclaw-interviewer admin candidate-bulk-remove --indices ...`
- 删除单个 candidate  
  `openclaw-interviewer admin candidate-remove --candidate-id <id>`
- 刷新 candidate  
  `openclaw-interviewer admin candidate-refresh --candidate-id <id>`
- 解析 resume  
  `openclaw-interviewer admin resume-parse ...`
- 生成岗位知识库  
  `openclaw-interviewer admin domain-generate ...`
- 检查 retrieval/RAG  
  `openclaw-interviewer admin retrieval-inspect`
- 跑 harness  
  `openclaw-interviewer harness --scenario <scenario>`

## 使用原则
1. 先读后写
2. 变更前确认目标对象
3. 优先保留审计痕迹
4. schema 不合法时不得落库
5. 对外部模型调用做校验、重试、fallback
6. 新增 candidate 前若缺少 `id / name / role / jd id or full jd / scheduled / resume path`，必须继续追问，不能自己补全

## 高风险动作
- 覆盖 candidate 主表
- 覆盖知识库/题库
- 删除候选人记录
- 覆盖 interview records
- 修改 config

这些动作必须谨慎说明影响范围。

## 禁止事项
- 不用 `openclaw-interviewer interview ...` 代替 live candidate lane
- 不把内部维护结果直接暴露给候选人
- 不跳过读取直接覆盖关键文件
- 不绕过 `./setup` 去猜路径或拼接绝对命令
- 不创建空简历、占位简历或虚构 JD 来凑齐命令参数
