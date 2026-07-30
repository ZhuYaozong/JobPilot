# MCP Tools 设计

## 概念

MCP（Model Context Protocol）中的 Tools 是允许 AI 模型与外部系统交互的标准化接口。每个 Tool 代表一个可执行操作，例如查询数据库、调用 API 或执行本地命令。Tools 通过定义输入参数和输出格式，使模型能够动态选择并调用合适的功能，从而扩展模型的行动能力。核心概念包括 Tool 描述（名称、描述、schema）、调用请求和响应，以及错误处理机制。

## 原理

MCP Tools 的工作原理基于请求-响应模型。客户端（AI 模型）通过发送包含 Tool 名称和参数的 JSON-RPC 请求来触发调用。服务器端注册的 Tool 处理该请求并返回结果。关键流程如下：
- **注册**：服务器使用 `registerTool` 方法注册 Tool，提供名称、描述和输入 JSON Schema。
- **调用**：客户端发送 `tools/call` 请求，携带 `name` 和 `arguments`。
- **执行**：服务器调用对应函数，执行操作并返回 `ToolResult`，包含 `content`（可能是文本、图像等）和可选 `isError` 标志。
- **错误处理**：若执行失败，返回 `isError: true` 及错误消息，客户端可据此进行重试或反馈。

## 实践案例

以“获取城市天气”工具为例。

### 架构流程
1. 服务器定义 `get_weather` Tool，输入参数 `city`（字符串）和 `unit`（枚举：celsius/fahrenheit）。
2. 客户端根据用户提问“北京的天气如何？”解析并调用 `get_weather`，参数 `{"city":"Beijing","unit":"celsius"}`。
3. 服务器调用第三方天气 API，获取实时数据，返回 `{"temperature": 22, "condition": "sunny", "humidity": 40}` 作为 `ToolResult`。
4. 客户端将结果格式化为自然语言回复。

### 关键参数
- `city`: 必填，字符串，支持中文名称。
- `unit`: 可选，默认 celsius，可选 fahrenheit。
- 超时限制：5000ms，超时返回 `timeout` 错误。

### 异常处理
- API 不可达：返回 `isError: true`，错误码 `API_UNAVAILABLE`，客户端提示“天气服务暂时不可用”。
- 城市不存在：返回 `isError: true`，错误码 `INVALID_CITY`，并提示用户重新输入。
- 参数校验失败：若 `city` 为空，返回参数错误。

### 监控指标
- 调用次数（每分钟、每小时）。
- 成功率（成功响应 / 总调用）。
- 平均响应时间（毫秒）。
- 错误分布（按错误类型统计）。

### 方案取舍
- 实时数据 vs 缓存：实时数据准确但增加延迟和 API 成本；缓存可提高响应速度但数据可能过时。本方案选择实时获取，并加入本地缓存（TTL=10分钟）以平衡。
- 同步 vs 异步：同步调用简单但阻塞；本场景使用同步以保证实时性。
- 单一工具 vs 多个小工具：将天气功能整合为一个工具，减少模型选择复杂度，但参数较多。
