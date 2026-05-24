"""推进投递阶段并写 ApplicationEvent 事件日志。

复用 ``transition_application_stage`` service,它会:
1) 校验投递归属当前用户
2) 更新 current_stage(及可选 next_action / next_action_at / notes)
3) 写一条 ApplicationEvent(event_type='stage_changed', from_stage, to_stage)

**重要安全约束**:operator_type 强制写 ``assistant``,不让 LLM 选;
这样事件审计里 Agent 操作与用户手动操作不会混淆。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext
from app.schemas.application_event import ApplicationTransitionRequest
from app.services.application_transition_service import transition_application_stage


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Application record not found": "application_record_not_found",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "application_record_not_found": (
        "投递记录不存在;请让用户确认 application_id,或先调用 list_user_applications。"
    ),
}


class UpdateApplicationStageToolArgs(BaseModel):
    """update_application_stage 工具入参。

    application_id / target_stage 在 schema 是 optional,_execute 强制检查。
    缺失时返回 missing_required_field 业务错。
    """

    application_id: int | None = Field(default=None, description="要推进的投递记录 id。")
    target_stage: str | None = Field(
        default=None,
        max_length=50,
        description=(
            "目标投递阶段:saved / applied / screening / assessment / interview / offer / "
            "rejected / withdrawn。"
        ),
    )
    next_action: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(
        default=None,
        description="可选,更新投递记录的 notes 字段(完整覆盖,非追加)。",
    )
    note: str | None = Field(
        default=None,
        description="可选,只写入本次阶段流转事件的备注(不影响投递主记录的 notes)。",
    )


_FIELD_LABELS: dict[str, str] = {
    "application_id": "投递记录 id",
    "target_stage": "目标阶段",
}


class UpdateApplicationStageTool(BaseTool):
    name = "update_application_stage"
    description = (
        "推进一条已存在投递记录的阶段(并写一条阶段流转事件)。"
        "用户说『把这条改成 interview』『标记成 offer』『更新到 applied 阶段』时使用。"
        "target_stage 必须是合法阶段枚举值。可选 next_action / notes 会覆盖投递主记录;"
        "可选 note 只写入本次阶段流转事件备注,适合记录『面试官反馈』『为什么拒绝』等。"
        "事件 operator_type 固定为 assistant,以便审计区分用户手动操作与 Agent 操作。"
        "**调用前必须确认 application_id 和 target_stage 都已知**:不知道 application_id "
        "先 list_user_applications;不清楚目标阶段先 respond_directly 追问用户。"
    )
    args_schema = UpdateApplicationStageToolArgs

    async def _execute(
        self,
        args: UpdateApplicationStageToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 必填字段缺失 → 业务错。
        missing: list[str] = []
        if args.application_id is None:
            missing.append("application_id")
        if not args.target_stage or not args.target_stage.strip():
            missing.append("target_stage")
        if missing:
            labels = ", ".join(_FIELD_LABELS[f] for f in missing)
            return {
                "ok": False,
                "error_class": "missing_required_field",
                "message_for_llm": (
                    f"缺少必填字段: {labels}。application_id 缺失请先 list_user_applications;"
                    f"target_stage 缺失请 respond_directly 追问用户想改到哪个阶段。"
                    f"**不要**自己猜测。"
                ),
                "user_facing_detail": f"缺少必填字段: {labels}",
                "missing_fields": missing,
            }

        # operator_type 强制 "assistant",不接收模型输入(避免 Agent 伪装成 user)。
        # 上面 missing 检查保证两个字段非空,这里直接 strip 不会 None。
        assert args.target_stage is not None
        assert args.application_id is not None
        request = ApplicationTransitionRequest(
            target_stage=args.target_stage.strip()[:50],
            next_action=args.next_action,
            notes=args.notes,
            note=args.note,
            operator_type="assistant",
        )
        try:
            application = await transition_application_stage(
                ctx.db,
                args.application_id,
                request,
                current_user=ctx.current_user,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        return {
            "ok": True,
            "data": {
                "application_id": application.id,
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
