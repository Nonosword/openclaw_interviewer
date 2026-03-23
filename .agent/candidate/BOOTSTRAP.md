# BOOTSTRAP.md

候选人侧首次启动说明。使用一次后可删除或归档。

## 启动步骤
1. 读取：
   - `ENTRYPOINT.json`
   - `AGENTS.md`
   - `IDENTITY.md`
   - `SOUL.md`
   - `TOOLS.md`
   - `USER.md`
2. 确认当前是 candidate-facing interview agent
3. 确认只处理候选人对话，不处理管理员维护
4. 确认当前目录同时包含 `SKILL.md`、`ENTRYPOINT.json`、`setup`、`openclaw-interviewer`、`config.yaml`
5. 若不满足，先切换到真正的 skill 根目录
6. 确认管理员已在当前 skill 根目录运行过 `./setup`
7. 确认项目 `.venv` 已创建，且 candidate workspace 中的 bootstrap 文档已经同步
8. 若未识别候选人，先使用：
   - `openclaw-interviewer interview identify ...`
9. 之后只使用 `openclaw-interviewer interview ...` 进入后续 workflow

## 禁止
- 不运行 `./setup`
- 不改用绝对路径
- 不运行旧兼容入口
- 不运行 `openclaw-interviewer admin ...`
- 不进入维护/初始化流程
