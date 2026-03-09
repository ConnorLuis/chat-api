
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version: str

class PromptRegistry:
    def __init__(self, prompts_dir: str):
        self.prompts_dir = Path(prompts_dir)

    def get(self, prompt_id: str, version: str) -> str:
        p = self.prompts_dir / prompt_id / f"{version}.md"
        if not p.exists():
            raise FileNotFoundError(f"prompt not found: {p}")
        return p.read_text(encoding="utf-8")

    def render(self, template: str, variables:dict[str, Any]| None) -> str:
        variables = variables or {}
        # 最小实现：Python format 替换。
        try:
            return template.format(**variables)
        except KeyError as e:
            missing = str(e).strip("'")
            # 缺变量就把占位符保留，避免直接报错
            return template.replace("{" + missing + "}", f"<missing:{missing}>")

try:
    # 这里按你的项目路径：src/app/llm/schemas.py
    from src.app.llm.schemas import ChatMessage
except Exception:  # pragma: no cover
    ChatMessage = None  # type: ignore

def ensure_system_prompt(messages: list[Any], system_text: str) -> list[Any]:
        """
        把 system prompt 插到 messages 最前面。
        - 若 messages 是 ChatMessage 列表：插入 ChatMessage(system,...)
        - 若 messages 是 dict 列表：插入 {"role":"system","content":...}
        """
        if messages and hasattr(messages[0], "role") and ChatMessage is not None:
            sys_msg = ChatMessage(role="system", content=system_text)
            return [sys_msg] + messages

        sys_msg = {"role": "system", "content": system_text}
        return [sys_msg] + messages