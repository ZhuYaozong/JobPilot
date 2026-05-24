"""草稿模式岗位:用户粘贴 JD 文本 或 输入岗位 URL,让 LLM 推断
公司名/岗位名/城市 + 结构化抽取。不落库,返给前端做"预览 → 编辑 → 保存"。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.job_parsing import JobParsingResult


class JobDraftRequest(BaseModel):
    """文本与 URL 二选一。

    两者都传时优先 URL(抓取后的正文比用户随手粘贴的更稳定);
    两者都空则报 422,在 schema 层拦下。
    """

    text: str | None = Field(default=None, description="JD 原文(粘贴模式)")
    url: str | None = Field(default=None, description="JD 网页链接(URL 模式)")

    @model_validator(mode="after")
    def _require_one(self) -> "JobDraftRequest":
        if not (self.text and self.text.strip()) and not (
            self.url and self.url.strip()
        ):
            raise ValueError("text 或 url 至少要提供一个")
        return self


class JobDraftResponse(BaseModel):
    company_name: str = Field(..., description="AI 推断的公司名,用户可改")
    job_title: str = Field(..., description="AI 推断的岗位名,用户可改")
    city: str | None = Field(default=None, description="可选,城市")
    jd_text: str = Field(..., description="JD 正文,作为 jd_text 落库")
    source_url: str | None = Field(default=None, description="URL 模式下回填")
    parsed_json: JobParsingResult = Field(
        ..., description="结构化抽取,直接作为 parsed_json 落库",
    )
