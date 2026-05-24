"""创建投递记录:把 (resume_id, job_posting_id) 绑定成一条 ApplicationRecord。

这是动作工具。典型场景:用户说"把腾讯那个标记成投递了""帮我记一下我用 v2 简历投了
ByteDance"。Agent 用 list_user_jobs / list_user_resumes 拿到 id 后调本工具落库。

不做去重(与 POST /api/v1/applications 一致):同一 (resume, job) 可以存在多条投递,
用户场景里偶尔会出现"重新投一次,记新一条"。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.models.application_record import ApplicationRecord
from app.services.user_scope_service import ensure_resume_and_job_exist_for_user


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
    "Job posting not found": "job_posting_not_found",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": "请求的简历不存在;请让用户确认 resume_id,或先调用 list_user_resumes。",
    "job_posting_not_found": "请求的岗位不存在;请让用户确认 job_posting_id,或先调用 list_user_jobs。",
}


class CreateApplicationToolArgs(BaseModel):
    resume_id: int = Field(..., description="投递使用的简历 id。")
    job_posting_id: int = Field(..., description="被投递的岗位 id。")
    current_stage: str = Field(
        default="saved",
        max_length=50,
        description=(
            "投递阶段枚举:saved / applied / screening / assessment / interview / offer / "
            "rejected / withdrawn。默认 saved。"
        ),
    )
    apply_channel: str | None = Field(default=None, max_length=100)
    next_action: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None)


class CreateApplicationTool(BaseTool):
    name = "create_application"
    description = (
        "创建一条新的投递记录,把指定简历和指定岗位绑定起来。"
        "用户说『帮我记一下投递了 X 公司』『把这条标记成投递了』『建一个 application』时使用。"
        "current_stage 默认 saved,可由用户指明(applied / interview / offer / rejected 等)。"
        "调用前确保已经有 resume_id 和 job_posting_id(必要时先 list_user_resumes / list_user_jobs)。"
        "**不做去重**,同一 (resume, job) 可以存在多条投递。"
    )
    args_schema = CreateApplicationToolArgs

    async def _execute(
        self,
        args: CreateApplicationToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # ensure_resume_and_job_exist_for_user 内部会用 get_*_for_user_or_404,
        # 失败时抛 HTTPException 404,统一转业务错。
        try:
            await ensure_resume_and_job_exist_for_user(
                ctx.db,
                resume_id=args.resume_id,
                job_posting_id=args.job_posting_id,
                current_user=ctx.current_user,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        application = ApplicationRecord(
            user_id=ctx.current_user.id,
            resume_id=args.resume_id,
            job_posting_id=args.job_posting_id,
            current_stage=args.current_stage.strip()[:50] or "saved",
            apply_channel=(args.apply_channel or None),
            next_action=(args.next_action or None),
            notes=args.notes,
        )

        try:
            ctx.db.add(application)
            await ctx.db.commit()
            await ctx.db.refresh(application)
        except SQLAlchemyError as exc:
            raise ToolSystemError(
                self.name,
                error_class="db_error",
                detail=str(exc),
            ) from exc

        return {
            "ok": True,
            "data": {
                "application_id": application.id,
                "resume_id": application.resume_id,
                "job_posting_id": application.job_posting_id,
                "current_stage": application.current_stage,
                "next_action": application.next_action,
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail, "unknown_business_error")
        return {
            "ok": False,
            "error_class": error_class,
            "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
            "user_facing_detail": detail,
        }
