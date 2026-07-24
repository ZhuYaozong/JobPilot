# MCP Resources 设计

## 概念

MCP（Model Context Protocol）中的 Resources 是指服务器可以暴露给客户端的数据对象，它们可以被客户端用于增强模型交互的上下文。Resources 类似于传统文件系统中的文件，每个资源由一个唯一的 URI 标识，并且可以包含文本或二进制内容。客户端可以通过标准化的协议操作来发现、读取或订阅资源的变化。Resources 的设计目的是让 AI 模型能够访问外部结构化的数据，例如文档、代码片段、数据库记录等，从而提升生成内容的相关性和准确性。

## 原理

Resources 的核心机制基于 URI 模式。每个资源都绑定一个 URI，该 URI 遵循自定义的 scheme（例如 `file://`、`db://` 等），并包含路径和可能的查询参数。服务器维护一个资源索引，记录每个 URI 对应的元数据，包括 `name`（显示名称）、`mimeType`（MIME 类型，如 `text/plain`、`application/json`）、`description`（可选描述）以及内容本身。客户端通过 `resources/list` 请求获取可用资源列表，通过 `resources/read` 请求读取特定资源的内容。服务器返回的内容通常包含 `contents` 数组，每个条目包括 `uri`、`mimeType` 和 `text`（或 `blob` 用于二进制）。Resources 可以是静态的（由服务器预先定义）或动态的（根据请求实时生成）。动态资源允许更灵活的数据访问，例如查询数据库或处理用户输入。

## 实践案例

实现一个基于文件系统的 MCP 资源服务器，提供目录列表和文件内容读取功能。

### 架构流程
1. 客户端发送 `resources/list` 请求，可选包含 `cursor` 参数进行分页。
2. 服务器接收请求，从文件系统读取指定根目录下的所有文件和子目录。
3. 服务器构建资源列表，每个资源包含 `uri`（如 `file:///home/user/docs/report.txt`）、`name`（文件名）、`mimeType`（根据扩展名映射）、`description`（文件大小和修改时间）。
4. 返回 `resources` 数组，若条目过多则使用 `nextCursor` 标记后续分页。
5. 客户端发送 `resources/read` 请求，携带 `uri` 参数。
6. 服务器验证 URI 合法性，检查文件存在且可读，读取文件内容。
7. 对于文本文件（如 .txt、.md），将内容放入 `text` 字段；对于二进制文件（如图片、PDF），使用 Base64 编码放入 `blob` 字段，并设置正确的 `mimeType`。
8. 返回包含 `contents` 数组的响应。

### 关键参数
- `uri`: 资源唯一标识，如 `file:///home/user/data.csv`。
- `mimeType`: 如 `text/csv`、`application/pdf`。
- `name`: 人类可读名称，例如 "2024-06-07_report.csv"。
- `description`: 可选，例如 "CSV 文件，包含销售数据，共 120KB"。
- 在列表请求中，`cursor` 参数用于分页。

### 异常处理
- 资源不存在：服务器返回错误码 `-32602`（Invalid params），并附带消息 “Resource not found”。
- 权限不足：对于无权限读取的文件，返回错误码 `-32001`（Unauthorized），并提示 “Access denied”。
- URI 格式无效：例如 scheme 不是 `file://`，返回 `-32600`（Invalid request）。
- 读取大文件时超时：限制最大文件大小（如 10MB），超过则返回错误 “File too large”。

### 监控指标
- `resources_list_requests`: 列表请求总数，用于分析访问模式。
- `resources_read_requests`: 读取请求总数。
- `resources_list_duration_ms`: 列表请求响应时间（平均值、P99）。
- `resources_read_duration_ms`: 读取请求响应时间。
- `resources_error_count`: 按错误类型分类的失败次数（NotFound、Unauthorized、Timeout）。
- `resources_cache_hit_rate`: 如果引入缓存，记录缓存命中率。

### 方案取舍
- **静态资源 vs 动态资源**：静态资源预先定义，响应速度快，但灵活性低；动态资源实时生成，可适应变化，但延迟较高。本案例选择动态实现以支持任意文件路径。
- **分页策略**：为避免大量资源一次性传输，使用基于游标的分页（cursor-based pagination）而非页码，避免数据变动导致偏移不准确。
- **二进制文件处理**：将二进制内容 Base64 编码会增加传输大小（约 33%），但符合 MCP 标准；对于大文件，可考虑提供流式传输（但当前 MCP 规范未支持，需等待扩展）。
- **安全性**：必须限制服务器可访问的根目录，避免路径遍历攻击（对 `..` 进行规范化检查）。
