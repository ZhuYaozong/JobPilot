# LangGraph 中 Checkpoint 持久化机制

## 概念

Checkpoint 持久化是 LangGraph 的核心功能之一，它允许在执行图（graph）的过程中定期保存状态快照。这些快照包含节点（node）的执行结果、边（edge）的决策以及全局配置，使得在故障、中断或动态扩展后能够从最近的检查点恢复执行，而无需重新运行整个图。Checkpoint 持久化类似于数据库中的检查点或分布式系统中的快照，为长周期、多步骤的 AI 工作流提供了可靠性和可恢复性。

## 原理

LangGraph 中的每个图执行都维护一个全局状态（State），状态由用户定义的结构化数据（如字典或 Pydantic 模型）构成。Checkpoint 持久化通过拦截每次节点执行完毕后的状态变化，将其序列化为快照并存储到持久化后端。核心机制包括：

1. **状态快照**：每当节点结束并修改状态后，LangGraph 会将当前状态、节点执行历史、待处理的边以及元数据（如时间戳、图 ID 和步骤编号）打包成一个 Checkpoint 对象。
2. **序列化与反序列化**：Checkpoint 使用 Python 的 `pickle` 或用户自定义的序列化器（如 JSON/MessagePack）将状态转为字节流。用户可通过 `checkpoint_serializer` 参数控制格式。
3. **存储后端**：LangGraph 提供几种内置持久化后端：内存（默认，进程内）、文件系统（本地目录）、SQLite、PostgreSQL 以及云存储（如 S3）。后端通过 `CheckpointSaver` 接口抽象，用户可自定义实现。
4. **恢复流程**：当执行中断（例如异常或手动暂停）后，可加载指定 `thread_id` 的最新 Checkpoint，LangGraph 会反序列化状态并重新建立图运行上下文，然后从最后完成的节点之后继续执行。

## 实践案例

假设我们需要构建一个多步骤的文档分析流水线：提取文本、摘要、关键词、情感分析。使用 Checkpoint 持久化确保在第三步失败后可从第二步恢复。

### 架构流程

- **图定义**：`State` 包含 `doc_text`, `summary`, `keywords`, `sentiment` 等字段。每个节点修改相应字段。
- **Checkpoint 集成**：在编译图时传入 `CheckpointSaver` 实例，例如 `FileSystemSaver(path="/tmp/checkpoints")`。
- **执行流程**：
  1. 启动图，传入初始 `doc_text`。
  2. 节点“extract_text”运行完成，自动保存 Checkpoint（包含当前全部状态）。
  3. 节点“generate_summary”消耗时间长，中途进程崩溃。
  4. 重启后，通过 `graph.resume(thread_id="abc123", checkpoint_id=None)` 加载最近 Checkpoint，从“extract_text”之后、“generate_summary”之前恢复。
  5. 重新运行“generate_summary”并继续后续节点。

### 关键参数

- **checkpoint_saver**：指定持久化后端对象，如 `SqliteSaver.from_conn_string("checkpoints.db")`。
- **checkpoint_serializer**：序列化器类型，可选 `JsonSerializer`（可读性高，但慢）或 `PickleSerializer`（快但版本敏感）。
- **thread_id**：唯一标识一次图执行，用于区分不同运行。
- **checkpoint_id**：指定要恢复的精确快照（默认最新）。
- **save_every_step**：布尔值，是否每步都保存（默认 True）。若设为 False，则只在显式调用 `save_checkpoint` 时保存。

### 异常处理

- 保存 Checkpoint 本身可能失败（磁盘满、网络超时）。建议在 Saver 中实现重试和回退策略（如先写临时文件再 rename）。
- 反序列化时可能因版本不兼容失败。使用 JSON 序列化可减少兼容问题，但需要确保状态可 JSON 序列化。
- 恢复时发现 Checkpoint 损坏：应记录错误并尝试前一个 Checkpoint（如果存在），或从头开始。
- 多线程同时写入同一 Checkpoint：后端应支持并发锁（如 SQLite 的 WAL 模式或 PostgreSQL 的行锁）。

### 监控指标

- **checkpoint_save_latency**：每次保存耗时，若超过阈值需优化。
- **checkpoint_size**：快照大小，避免过大影响性能。
- **recovery_success_rate**：成功恢复的比例。
- **checkpoint_count**：单个 thread 的 Checkpoint 数量，过多需清理策略（保留最近 N 个）。
- **storage_usage**：后端存储空间占用。

### 方案取舍

- **内存 vs 持久化后端**：内存最快但无持久性，适合短时实验；文件系统简单可靠但不易共享；SQLite/PostgreSQL 支持并发和远程访问。
- **序列化格式**：Pickle 快但版本敏感，JSON 慢但跨版本兼容。对于生产环境，建议使用 JSON 并控制状态大小。
- **保存频率**：每步保存开销大，但恢复粒度细；按需保存可提升性能，但丢失更多进度。
- **清理策略**：保留全部 Checkpoint 占用大量空间，应基于时间或数量淘汰。LangGraph 不提供自动清理，用户需定期删除老旧文件。

通过以上设计，Checkpoint 持久化为 LangGraph 工作流提供了弹性恢复能力，是构建可靠 AI 服务的关键组件。
