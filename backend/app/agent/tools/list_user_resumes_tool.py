"""只读工具：把当前用户的简历列表暴露给 Agent。"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_adapter import BaseTool, ToolContext
from app.models.resume import Resume


class ListUserResumesArgs(BaseModel):
    query: str | None = Field(
        default=None,
        description="Optional case-insensitive substring to match against resume title.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class ListUserResumesTool(BaseTool):
    name = "list_user_resumes"
    description = (
        "List the user's resumes. Returns id, title, parse_status, and source_type"
        " for each. Use this when the user refers to a resume vaguely (e.g. '我"
        "最新的简历') and you need the resume_id for downstream tools. The"
        " optional 'query' filters by title substring."
    )
    args_schema = ListUserResumesArgs

    async def _execute(
        self,
        args: ListUserResumesArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 中文说明：列表工具只返回定位下游动作所需字段，不把简历正文暴露给 decide prompt。
        statement = select(
            Resume.id,
            Resume.title,
            Resume.parse_status,
            Resume.source_type,
            Resume.updated_at,
        ).where(Resume.user_id == ctx.current_user.id)

        if args.query:
            # 中文说明：这里是标题子串过滤，不做全文检索；简历正文分析由 parse/match 工具完成。
            statement = statement.where(Resume.title.ilike(f"%{args.query}%"))

        statement = statement.order_by(
            Resume.updated_at.desc(), Resume.id.desc(),
        ).limit(args.limit)

        rows = (await ctx.db.execute(statement)).all()

        # 中文说明：DTO 手工构造，避免 ORM from_attributes 在 async session 下触发 MissingGreenlet。
        resumes = [
            {
                "id": row.id,
                "title": row.title,
                "parse_status": row.parse_status,
                "source_type": row.source_type,
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": {"resumes": resumes, "count": len(resumes)},
        }
