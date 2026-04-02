# BOOTSTRAP.md

管理员侧首次启动说明。使用一次后可删除或归档。

## 启动步骤

1. 确认当前目录同时包含 `SKILL.md`、`ENTRYPOINT.json`、`setup`、`openclaw-interviewer`、`config.yaml`
2. 若不满足，先切换到真正的 skill 根目录
3. 在 skill 根目录运行 `./setup`
4. 确认项目 `.venv` 已创建
5. 读取：
   - `ENTRYPOINT.json`
   - `AGENTS.md`
   - `IDENTITY.md`
   - `TOOLS.md`
   - `USER.md`
   - `SOUL.md`
6. 运行 `openclaw-interviewer doctor`

## 启动后目标
- 能可靠维护 candidate / resume / domain / question bank
- 能指导测试、harness、排障
- 不混用候选人侧规则
