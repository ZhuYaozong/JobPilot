"""把"创建岗位"封装成 Agent 工具。

create_job 属于动作工具:直接写入 JobPostings 表。典型 ReAct 链路:
draft_job 拿到草稿 → respond_directly 让用户确认 → 用户同意后调用本工具。

工具刻意不再调 LLM:草稿阶段已经把 parsed_json 准备好,这里只做落库,
避免对话里同一份内容被解析两次。如果 LLM 没有提供 parsed_json,新岗位的 parsed_json
列就是 NULL,Agent / 前端可后续手动触发解析(JobPosting 没有独立的 parse_status 列,
解析与否由 parsed_json 是否为 NULL 推断,与 list_user_jobs 行为一致)。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.models.job_posting import JobPosting


class CreateJobToolArgs(BaseModel):
    """create_job 工具入参。

    字段对齐 ``JobPostingCreate``;parsed_json 可选,通常来自 draft_job 的输出。

    company_name / job_title / jd_text 在 schema 层是 optional,但 _execute 里会强制检查
    并返回 missing_required_field 业务错,引导 Agent 用 respond_directly 向用户追问,
    而不是抛 ToolValidationError 走 decide repair。
    """

    company_name: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    jd_text: str | None = Field(default=None, description="JD 原文,作为 jd_text 落库。")
    city: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=1024)
    # 任意 JSON 结构,通常是 draft_job 返回的 parsed_json。带上时不会再触发解析。
    parsed_json: dict[str, Any] | None = Field(
        default=None,
        description=(
            "可选;通常直接复用 draft_job 返回的 parsed_json。"
            "传入时一并落库并把 parse_status 标记为 parsed。"
        ),
    )


# 字段技术名 → 给用户看的中文名,失败时拼到 message_for_llm 里让 Agent 自然追问。
_FIELD_LABELS: dict[str, str] = {
    "company_name": "公司名",
    "job_title": "岗位名",
    "jd_text": "JD 正文",
}


class CreateJobTool(BaseTool):
    name = "create_job"
    description = (
        "把已经确认的岗位信息直接写入数据库。通常承接 draft_job 的输出:"
        "用户确认草稿后,把 draft_job 返回的 company_name / job_title / city / "
        "jd_text / source_url / parsed_json 原样传给本工具。"
        "传入 parsed_json 时新岗位会标记为 parsed,无需再调用解析。"
        "**调用前必须确认 company_name / job_title / jd_text 都已知**,缺任何一项请先"
        "respond_directly 向用户追问,而不是用空串或猜测值调用本工具。"
    )
    args_schema = CreateJobToolArgs

    async def _execute(
        self,
        args: CreateJobToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # write 工具的"必填字段缺失"统一走业务错,让 LLM 转 respond_directly 询问用户。
        missing: list[str] = [
            field for field in ("company_name", "job_title", "jd_text")
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

        # 整体字段映射跟 POST /jobs 保持一致;parsed_json 为 None 时不写,
        # 保留数据库列的默认值。status 不暴露给模型,统一用 "active" 默认。
        # 上面的 missing 检查已经保证三个字段非空,这里直接 strip 不会 None。
        job = JobPosting(
            user_id=ctx.current_user.id,
            company_name=args.company_name.strip()[:255],  # type: ignore[union-attr]
            job_title=args.job_title.strip()[:255],  # type: ignore[union-attr]
            jd_text=args.jd_text,
            city=(args.city or "").strip()[:100] or None,
            source_url=(args.source_url or None),
            status="active",
        )
        if args.parsed_json is not None:
            job.parsed_json = args.parsed_json

        try:
            ctx.db.add(job)
            await ctx.db.commit()
            await ctx.db.refresh(job)
        except SQLAlchemyError as exc:
            # 数据库异常属于系统错;tool_adapter 会做 rollback 并写 failed 日志。
            raise ToolSystemError(
                self.name,
                error_class="db_error",
                detail=str(exc),
            ) from exc

        return {
            "ok": True,
            "data": {
                "job_posting_id": job.id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "city": job.city,
                # JobPosting 没有 parse_status 列;沿用 list_user_jobs 的派生方式。
                "parse_status": "parsed" if job.parsed_json else "pending",
            },
        }
