# BOOTSTRAP.md

管理员侧首次启动说明。使用一次后可删除或归档。

## 启动步骤
1. 读取：
   - `ENTRYPOINT.json`
   - `AGENTS.md`
   - `IDENTITY.md`
   - `TOOLS.md`
   - `USER.md`
   - `SOUL.md`
2. 确认当前是 admin-facing operations agent
3. 确认当前目录同时包含 `SKILL.md`、`ENTRYPOINT.json`、`setup`、`openclaw-interviewer`、`config.yaml`
4. 若不满足，先切换到真正的 skill 根目录
5. 在 skill 根目录运行 `./setup`
6. 确认项目 `.venv` 已创建
8. 确认 `./openclaw-interviewer` 已被创建或修复
9. 运行 `openclaw-interviewer doctor`
10. 之后优先执行：
   - `openclaw-interviewer admin capabilities-list`
   - `openclaw-interviewer admin candidate-list`
   - `openclaw-interviewer admin candidate-initialize`
11. 测试时可运行：
   - `openclaw-interviewer harness --scenario admin_ops`
   - `openclaw-interviewer harness --scenario full_interview`

## 启动后目标
- 能可靠维护 candidate / resume / domain / question bank
- 能指导测试、harness、排障
- 不混用候选人侧规则
