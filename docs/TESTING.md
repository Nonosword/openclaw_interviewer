# TESTING

当前项目提供三类主要验证方式。

## 1. 统一入口 smoke
```bash
./setup
openclaw-interviewer doctor
openclaw-interviewer admin capabilities-list
openclaw-interviewer admin retrieval-inspect
openclaw-interviewer admin candidate-initialize
```

## 2. Skill Harness
### full interview
```bash
openclaw-interviewer harness --scenario full_interview
```

### security probe
```bash
openclaw-interviewer harness --scenario security_probe
```

### admin ops
```bash
openclaw-interviewer harness --scenario admin_ops
```

### transcript replay
```bash
openclaw-interviewer harness \
  --scenario transcript_replay \
  --transcript-file tests/sample_answers.txt
```

## 3. 仓库级单测
```bash
python3 -m unittest discover -s tests -v
```

## 如何看 Harness 输出
Harness 输出包含：
- `traces`：endpoint / adapter 调用链
- `step_traces`：workflow step 链
- `transcript`：对外可见过程摘要
- `final_record`：最终记录（若有）
- `status`：最终 runtime 状态
- `errors`：失败原因
