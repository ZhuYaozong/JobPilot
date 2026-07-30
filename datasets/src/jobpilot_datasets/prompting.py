"""从 prompts 目录加载并渲染模板。"""

from __future__ import annotations

from pathlib import Path
from string import Template


class PromptRepository:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def render(self, name: str, **values: object) -> str:
        path = self.directory / name
        template = Template(path.read_text(encoding="utf-8"))
        return template.substitute(
            {key: str(value) for key, value in values.items()},
        )
