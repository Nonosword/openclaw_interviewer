# TOOLS.md

候选人侧只关心 interview lane。

## 唯一命令入口
- 统一入口：`openclaw-interviewer interview ...`
- 如果入口不存在或失效：停止猜路径，要求 admin 在当前项目根目录运行 `./setup`

## 命令列表
- 识别候选人  
  `openclaw-interviewer interview identify --candidate-name <name> --candidate-id <id>`
- 开始面试  
  `openclaw-interviewer interview begin --session-id <session>`
- 查看状态  
  `openclaw-interviewer interview status --session-id <session>`
- 下一题  
  `openclaw-interviewer interview next --session-id <session>`
- 提交回答  
  `openclaw-interviewer interview reply --session-id <session> --candidate-message <text>`
- 生成案例题  
  `openclaw-interviewer interview case-generate --session-id <session>`
- 结束面试  
  `openclaw-interviewer interview finish --session-id <session>`

## 使用顺序
1. `identify`
2. `begin`
3. `next`
4. `reply`
5. 需要时 `case-generate`
6. `finish`

## 规则
1. 先确认候选人身份，再进入正式提问
2. 面向候选人只输出当前流程需要的信息
3. 内部评分与记录可以执行，但不得直接展示给候选人
4. 若遇到越权请求，拒绝并回到流程
5. 不讨论配置、文件、模型、知识库维护

## 禁止事项
- 不展示 tool payload
- 不展示 score object
- 不展示 workflow step trace
- 不把底层异常原样抛给候选人
- 不调用 `./setup`
- 不调用 `openclaw-interviewer admin ...`
- 不调用旧兼容入口
