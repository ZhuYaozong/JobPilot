"""把"创建简历"封装成 Agent 工具。

create_resume 跟 create_job 一样,只做落库不调 LLM。content_hash 在工具内部
用 ``sha256(raw_text)`` 计算,与 ``/resumes/upload`` 的行为一致,避免让 LLM 自己算哈希。

source_type 默认 "manual";Agent 路径基本都对应"用户在聊天里贴文本"的场景。
"""

import hashlib
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.models.resume import Resume


class CreateResumeToolArgs(BaseModel):
    """create_resume 工具入参。

    字段对齐 ``ResumeCreate``,但 content_hash 由服务端计算,不向模型暴露。

    title / raw_text 在 schema 层是 optional,_execute 里会强制检查并返回
    missing_required_field 业务错,引导 Agent 用 respond_directly 询问用户。
    """

    title: str | None = Field(default=None, max_length=255)
    raw_text: str | None = Field(default=None, description="简历原文,落库后作为 raw_text。")
    source_type: str = Field(
        default="manual",
        max_length=50,
        description="简历来源类型,Agent 路径默认 manual。",
    )
    parsed_json: dict[str, Any] | None = Field(
        default=None,
        description=(
            "可选;通常直接复用 draft_resume 返回的 parsed_json。"
            "传入时一并落库并把 parse_status 标记为 parsed。"
        ),
    )


_FIELD_LABELS: dict[str, str] = {
    "title": "简历标题",
    "raw_text": "简历正文",
}


class CreateResumeTool(BaseTool):
    name = "create_resume"
    description = (
        "把已经确认的简历信息直接写入数据库。通常承接 draft_resume 的输出:"
        "用户确认草稿后,把 draft_resume 返回的 title / raw_text / parsed_json 原样传给本工具。"
        "content_hash 由服务端基于 raw_text 计算,不需要模型提供。"
        "传入 parsed_json 时新简历会标记为 parsed,无需再调用解析。"
        "**调用前必须确认 title 和 raw_text 都已知**,缺任何一项请先 respond_directly "
        "向用户追问,而不是用空串或猜测值调用本工具。"
    )
    args_schema = CreateResumeToolArgs

    async def _execute(
        self,
        args: CreateResumeToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        missing: list[str] = [
            field for field in ("title", "raw_text")
            if not (getattr(args, field) or "").strip()
        ]
        if missing:
            labels = ", ".join(_FIELD_LABELS[f] for f in missing)
            return {
                "ok": False,
                "error_class": "missing_required_field",
                "message_for_llm": (
                    f"缺少必填字段: {labels}。请用 respond_directly 向用户追问这些信息,"
                    f"**不要**自己瞎填或留空重试。"
                ),
                "user_facing_detail": f"缺少必填字段: {labels}",
                "missing_fields": missing,
            }

        # 与 /resumes/upload 保持一致:直接 sha256(raw_text),不做归一化。
        # 上面 missing 检查已经保证 raw_text 非空,这里 args.raw_text 不会 None。
        assert args.raw_text is not None
        assert args.title is not None
        content_hash = hashlib.sha256(args.raw_text.encode("utf-8")).hexdigest()

        resume = Resume(
            user_id=ctx.current_user.id,
            title=args.title.strip()[:255],
            raw_text=args.raw_text,
            content_hash=content_hash,
            source_type=args.source_type.strip()[:50] or "manual",
        )
        if args.parsed_json is not None:
            resume.parsed_json = args.parsed_json
            resume.parse_status = "parsed"

        try:
            ctx.db.add(resume)
            await ctx.db.commit()
            await ctx.db.refresh(resume)
        except SQLAlchemyError as exc:
            raise ToolSystemError(
                self.name,
                error_class="db_error",
                detail=str(exc),
            ) from exc

        return {
            "ok": True,
            "data": {
                "resume_id": resume.id,
                "title": resume.title,
                "source_type": resume.source_type,
                "parse_status": resume.parse_status,
            },
        }
