"""只读工具：把当前用户的投递记录暴露给 Agent。"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_adapter import BaseTool, ToolContext
from app.models.application_record import ApplicationRecord


class ListUserApplicationsArgs(BaseModel):
    current_stage: str | None = Field(
        default=None,
        description=(
            "可选。按投递阶段精确过滤，例如 saved、applied、interview 等枚举值。"
        ),
    )
    limit: int = Field(default=20, ge=1, le=100)


class ListUserApplicationsTool(BaseTool):
    name = "list_user_applications"
    description = (
        "列出当前用户的投递记录(resume + job_posting + stage)。每条返回 id、"
        "resume_id、job_posting_id、current_stage、next_action、next_action_at。"
        "当用户询问“我的投递”或“我投过的这个岗位”时使用。可选参数 current_stage "
        "用于按阶段过滤。"
    )
    args_schema = ListUserApplicationsArgs

    async def _execute(
        self,
        args: ListUserApplicationsArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 中文说明：投递列表只暴露 id、关联对象和阶段信息，避免把备注等长文本塞进工具观察。
        statement = select(
            ApplicationRecord.id,
            ApplicationRecord.resume_id,
            ApplicationRecord.job_posting_id,
            ApplicationRecord.current_stage,
            ApplicationRecord.next_action,
            ApplicationRecord.next_action_at,
            ApplicationRecord.applied_at,
        ).where(ApplicationRecord.user_id == ctx.current_user.id)

        if args.current_stage:
            # 中文说明：阶段过滤是精确匹配，避免模型用模糊阶段词误命中错误投递。
            statement = statement.where(
                ApplicationRecord.current_stage == args.current_stage,
            )

        statement = statement.order_by(
            ApplicationRecord.updated_at.desc(), ApplicationRecord.id.desc(),
        ).limit(args.limit)

        rows = (await ctx.db.execute(statement)).all()

        # 中文说明：时间字段转 ISO 字符串，保证 ToolCallLog 和 prompt 里的结果可 JSON 序列化。
        applications = [
            {
                "id": row.id,
                "resume_id": row.resume_id,
                "job_posting_id": row.job_posting_id,
                "current_stage": row.current_stage,
                "next_action": row.next_action,
                "next_action_at": (
                    row.next_action_at.isoformat() if row.next_action_at else None
                ),
                "applied_at": row.applied_at.isoformat() if row.applied_at else None,
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": {"applications": applications, "count": len(applications)},
        }
