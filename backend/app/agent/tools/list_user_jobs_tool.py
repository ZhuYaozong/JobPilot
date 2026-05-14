"""只读工具：把当前用户的岗位列表暴露给 Agent。

典型 ReAct 用法：用户只说公司或岗位名称，没有提供 job_posting_id 时，模型先带
``query`` 调用此工具查出 id，再继续调用 analyze_match、generate_cover_letter 等动作工具。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.agent.tool_adapter import BaseTool, ToolContext
from app.models.job_posting import JobPosting


class ListUserJobsArgs(BaseModel):
    query: str | None = Field(
        default=None,
        description=(
            "可选。用于匹配 company_name 或 job_title 的大小写不敏感子串。"
            "当用户提到公司或岗位名称但没有提供 job_posting_id 时使用。"
        ),
    )
    limit: int = Field(default=20, ge=1, le=100)


class ListUserJobsTool(BaseTool):
    name = "list_user_jobs"
    description = (
        "列出当前用户保存的岗位。每条返回 id、company_name、job_title、city、status、"
        "parse_status。当用户用名称指代岗位(例如“腾讯的后端岗位”)且后续工具需要"
        " job_posting_id 时使用。可选参数 query 会按公司或岗位标题子串过滤。"
    )
    args_schema = ListUserJobsArgs

    async def _execute(
        self,
        args: ListUserJobsArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 只 select Agent 需要的列，避免 ORM 对象进入 Pydantic/LLM 路径引发异步 lazy load。
        statement = select(
            JobPosting.id,
            JobPosting.company_name,
            JobPosting.job_title,
            JobPosting.city,
            JobPosting.status,
            JobPosting.parsed_json,
        ).where(JobPosting.user_id == ctx.current_user.id)

        if args.query:
            like = f"%{args.query}%"
            # query 只做轻量模糊过滤，不承担复杂搜索；真正语义检索走知识库工具。
            statement = statement.where(
                or_(
                    JobPosting.company_name.ilike(like),
                    JobPosting.job_title.ilike(like),
                ),
            )

        statement = statement.order_by(
            JobPosting.updated_at.desc(), JobPosting.id.desc(),
        ).limit(args.limit)

        rows = (await ctx.db.execute(statement)).all()

        # 返回紧凑 DTO，既给模型足够 disambiguation，也避免把完整 JD 塞进 prompt。
        jobs = [
            {
                "id": row.id,
                "company_name": row.company_name,
                "job_title": row.job_title,
                "city": row.city,
                "status": row.status,
                "parse_status": "parsed" if row.parsed_json else "pending",
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": {"jobs": jobs, "count": len(jobs)},
        }
