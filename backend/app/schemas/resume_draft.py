"""草稿模式:用户粘贴一段简历文本,让 LLM 推断标题 + 结构化抽取。

刻意不落库:返回给前端,经用户审阅修改后再走常规 POST /resumes 创建。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.resume_parsing import ResumeParsingResult


class ResumeDraftRequest(BaseModel):
    text: str = Field(..., min_length=1, description="用户粘贴的简历正文")


class ResumeDraftResponse(BaseModel):
    title: str = Field(..., description="AI 建议的简历标题,用户可改")
    raw_text: str = Field(..., description="保留为后续 raw_text 写入数据库")
    parsed_json: ResumeParsingResult = Field(
        ..., description="结构化抽取结果,直接作为 parsed_json 落库",
    )
