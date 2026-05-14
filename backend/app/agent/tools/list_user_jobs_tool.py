"""只读工具：把当前用户的岗位列表暴露给 Agent。

ReAct-style usage: when a user mentions a company name but no job_posting_id,
the LLM can call this with ``query="...company..."`` to look up the id before
calling analyze_match / generate_cover_letter / etc.
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
            "Optional case-insensitive substring to match against company name"
            " or job title. Use to narrow results when the user mentioned a"
            " company or role."
        ),
    )
    limit: int = Field(default=20, ge=1, le=100)


class ListUserJobsTool(BaseTool):
    name = "list_user_jobs"
    description = (
        "List the user's saved job postings. Returns id, company_name, job_title,"
        " city, status, and parse_status for each. Use this when the user refers"
        " to a job by name (e.g. '腾讯的后端岗位') and you need the job_posting_id"
        " for downstream tools. The optional 'query' argument filters by company"
        " or title substring."
    )
    args_schema = ListUserJobsArgs

    async def _execute(
        self,
        args: ListUserJobsArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 中文说明：只 select Agent 需要的列，避免 ORM 对象进入 Pydantic/LLM 路径引发异步 lazy load。
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
            # 中文说明：query 只做轻量模糊过滤，不承担复杂搜索；真正语义检索走知识库工具。
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

        # 中文说明：返回紧凑 DTO，既给模型足够 disambiguation，也避免把完整 JD 塞进 prompt。
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
