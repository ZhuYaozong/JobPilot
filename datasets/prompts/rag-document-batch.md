请为下面每个槽位生成一篇独立 Markdown 文档：

$slots_json

每篇要求：
- 正文去除 Markdown 标记和空白后为 $min_chars 到 $max_chars 个字符。
- 必须包含一级标题，以及“## 概念”“## 原理”“## 实践案例”三个章节。
- 实践案例需要有架构流程、关键参数、异常处理、监控指标和方案取舍。
- 不得出现 TODO、占位符或“作为 AI”。
- plan_id 必须原样返回。

返回格式：
{"items":[{"plan_id":"原样返回槽位ID","title":"文档标题","markdown":"# 标题\n\n## 概念\n..."}]}

$rejection_feedback
