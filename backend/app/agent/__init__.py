"""JobPilot Agent 运行时模块。

这里放 LangGraph 工作流、工具适配层、工具注册表和提示词构造逻辑。
业务规则仍然沉在 ``app.services``，Agent 层只负责编排、参数校验和运行追踪。
"""
