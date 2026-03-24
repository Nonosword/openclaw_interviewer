from __future__ import annotations

import re

BLOCKED_PATTERNS = [
    r"评分规则", r"打分规则", r"理想答案", r"系统提示", r"系统提示词", r"prompt", r"system prompt", r"developer message",
    r"knowledge_id", r"endpoint",
    r"显示.*内部", r"导出.*内部", r"忽略.*规则", r"覆盖.*规则", r"修改.*规则",
    r"给我看.*json", r"score_records", r"manifest", r"题库来源",
]


class SecurityPolicy:
    def is_internal_probe(self, text: str) -> bool:
        text = text or ""
        lowered = text.lower()
        if any(h in lowered for h in ["ignore previous", "reveal prompt", "show internal", "system prompt"]):
            return True
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in BLOCKED_PATTERNS)
