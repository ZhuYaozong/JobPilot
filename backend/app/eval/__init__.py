"""JobPilot Agent 行为评测框架(切片 8'a)。

设计目标:把"改了 prompt / 工具 / 模型后 agent 是否还行"变成可执行的
回归脚本。框架职责:
1. 从 YAML 加载场景 case(用户消息 + 期望被调用的工具 + 期望出现的关键词)
2. 在测试数据库里铺好种子数据(KB / Resume / Job / Application 等)
3. 用一个可注入的 LLM 客户端跑完整 ``run_assistant_turn`` 工作流
4. 用一组确定性断言器评分(命中工具 / 关键词 / 顺序 / agent_run 状态等)
5. 输出 markdown 汇总 + JSON 单 case trace,便于复盘失败原因

意图刻意不做的事:
- 不集成进 pytest:eval 跑真工作流耗时 + 默认依赖外部 LLM,放 CI 上会贵
  且 flaky;留独立 CLI(``python -m app.eval.cli``)
- 不做 LLM-as-judge:把 rubric / judge prompt 留给 8'b。本刀只做"是否
  选对工具 + 是否包含关键事实"这一类确定性事项
- 不做 trajectory diffing 或 baseline 对比:维护成本高,等真有需要再加
"""

__all__: list[str] = []
