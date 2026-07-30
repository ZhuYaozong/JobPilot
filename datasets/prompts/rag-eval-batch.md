源文档路径：$source_document

源文档：
--- DOCUMENT START ---
$document_content
--- DOCUMENT END ---

请为以下槽位各生成一条独立 RAG 测试：
$slots_json

约束：
- answer 为 $answer_min 到 $answer_max 个有效字符。
- answer 建议写成 60~160 字的完整解释，至少包含“条件/做法/结果”中的两个方面；不得只返回数字、协议名或单个短语。
- 如果某个槽位只能生成不足 $answer_min 字的答案，请改问文档中的机制、步骤、原因或异常处置，不要缩短答案。
- supporting_excerpt 为源文档中连续存在的原文，长度 $excerpt_min 到 $excerpt_max 个有效字符。
- supporting_excerpt 必须从 DOCUMENT 中逐字复制一段连续文本，禁止改写、跨段拼接、添加省略号或自行纠正原文。
- 不得询问文档标题、章节数量等无业务价值问题。
- plan_id 必须原样返回。
- 输出 JSON 前逐项检查：answer 字数达标、excerpt 可在 DOCUMENT 中直接搜索到、plan_id 无遗漏。

返回格式：
{"items":[{"plan_id":"原样返回槽位ID","question":"","answer":"","supporting_excerpt":""}]}

$rejection_feedback
