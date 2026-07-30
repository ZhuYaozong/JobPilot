请为下面的生成槽位各生成一条且只生成一条记录：

$slots_json

约束：
- instruction 为真实面试官问题，不能与同批其他问题同义改写。
- input 是补充场景；无必要时允许为空字符串，但字段必须存在。
- output 使用中文，去除空白后必须在 $answer_min 到 $answer_max 个字符之间。
- 每条回答必须包含工程落地细节，并说明至少一个失败处理、指标、参数或方案取舍。
- 问题必须忠实于槽位中的 task_type、topic、difficulty、scenario。

返回格式：
{"items":[{"plan_id":"原样返回槽位ID","instruction":"","input":"","output":""}]}

$rejection_feedback
