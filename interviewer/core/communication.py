from __future__ import annotations


class Communicator:
    def ask_identity(self) -> str:
        return "请先确认你的姓名和候选人编号。"

    def identify_fail(self) -> str:
        return "未找到匹配的候选人信息，请确认姓名和候选人编号后再试。"

    def identify_success(self, name: str, cid: str, role: str, scheduled_at: str) -> str:
        return f"已确认候选人信息：姓名 {name}，编号 {cid}，面试岗位 {role}，预约时间 {scheduled_at}。"

    def begin(self, is_late: bool) -> str:
        return "已到面试时间，当前记录为迟到进入。本轮面试现在开始。" if is_late else "好的，身份已确认。本轮面试现在开始。"

    def ask_question(self, question: str) -> str:
        return question

    def followup(self, question: str) -> str:
        return question

    def denied(self) -> str:
        return "这个请求不在面试可讨论范围内。我们继续当前面试内容。"

    def finish(self) -> str:
        return "好的，本轮面试到这里结束，结果将由后续流程统一处理。"
