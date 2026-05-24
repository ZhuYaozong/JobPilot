"""列出已经生成过的求职材料(求职信 / 面试准备 等)。

避免 Agent 在用户问"我之前的求职信呢"时重复 generate_cover_letter。
返回紧凑列表(不含 content_text),用户想看具体内容时,产品当前有
GET /api/v1/artifacts/{id} 端点,本刀不为 Agent 加 read_artifact(留作未来观察)。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_adapter import BaseTool, ToolContext
from app.models.generated_artifact import GeneratedArtifact


class ListGeneratedArtifactsToolArgs(BaseModel):
    resume_id: int | None = Field(
        default=None,
        description="可选。只列出关联此 resume_id 的材料。",
    )
    job_posting_id: int | None = Field(
        default=None,
        description="可选。只列出关联此 job_posting_id 的材料。",
    )
    artifact_type: str | None = Field(
        default=None,
        max_length=50,
        description=(
            "可选。按类型过滤:cover_letter / interview_prep 等。不传则全部类型。"
        ),
    )
    limit: int = Field(default=20, ge=1, le=100)


class ListGeneratedArtifactsTool(BaseTool):
    name = "list_generated_artifacts"
    description = (
        "列出当前用户已经生成过的求职材料(求职信 / 面试准备 等)。"
        "用户问『我之前给 X 公司写的求职信呢』『我准备过的面试材料』时使用,"
        "避免重复 generate_cover_letter / generate_interview_prep。"
        "可按 resume_id / job_posting_id / artifact_type 过滤;返回紧凑列表"
        "(id、artifact_type、title、resume_id、job_posting_id、status、created_at),"
        "**不含正文**。需要看正文时引导用户到前端 artifacts 详情页查看。"
    )
    args_schema = ListGeneratedArtifactsToolArgs

    async def _execute(
        self,
        args: ListGeneratedArtifactsToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 只 select 列表所需列,避免把 content_text(可能 KB 级别)拉进工具结果。
        statement = select(
            GeneratedArtifact.id,
            GeneratedArtifact.artifact_type,
            GeneratedArtifact.title,
            GeneratedArtifact.resume_id,
            GeneratedArtifact.job_posting_id,
            GeneratedArtifact.application_record_id,
            GeneratedArtifact.status,
            GeneratedArtifact.generator_type,
            GeneratedArtifact.created_at,
        ).where(GeneratedArtifact.user_id == ctx.current_user.id)

        if args.resume_id is not None:
            statement = statement.where(GeneratedArtifact.resume_id == args.resume_id)
        if args.job_posting_id is not None:
            statement = statement.where(
                GeneratedArtifact.job_posting_id == args.job_posting_id,
            )
        if args.artifact_type:
            statement = statement.where(
                GeneratedArtifact.artifact_type == args.artifact_type.strip()[:50],
            )

        statement = statement.order_by(
            GeneratedArtifact.created_at.desc(),
            GeneratedArtifact.id.desc(),
        ).limit(args.limit)

        rows = (await ctx.db.execute(statement)).all()

        artifacts = [
            {
                "id": row.id,
                "artifact_type": row.artifact_type,
                "title": row.title,
                "resume_id": row.resume_id,
                "job_posting_id": row.job_posting_id,
                "application_record_id": row.application_record_id,
                "status": row.status,
                "generator_type": row.generator_type,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": {"artifacts": artifacts, "count": len(artifacts)},
        }
