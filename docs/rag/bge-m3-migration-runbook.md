# BGE-M3 1536→1024 维迁移运行手册

## 为什么需要迁移

旧知识库列是 `vector(1536)`，BGE-M3 dense embedding 固定返回 1024 维。pgvector 固定维度列不能写入不同长度的向量，而且不同模型的向量空间没有可比性，因此不能通过截断、补零或类型转换复用旧向量。

迁移 `e8f3a1c9d204` 会保留文档、chunk 文本、归属和元数据，但会清空旧 embedding、把列改为 `vector(1024)` 并重建 HNSW 索引。迁移期间 BM25 仍可使用保存下来的 chunk 文本。

## 当前审计基线

2026-07-30 在本地数据库上得到以下迁移前基线：

| 项目 | 数量/状态 |
| --- | ---: |
| Alembic revision | `d4a7c9e2b610` |
| 向量列 | `vector(1536)` |
| 文档总数 | 1094 |
| `ready` 文档 | 795 |
| chunk 总数 | 1005 |
| 有 embedding 的 chunk | 873 |
| 默认迁移重建候选 | 795 |

这些数字用于本次切换前后的完整性核对，不是代码中的固定断言。后续如果继续写入文档，实际数量会变化，应重新审计。

## 一、备份与校验

迁移会主动清空旧向量，必须先做 PostgreSQL custom-format 备份。PowerShell 5.1 不应使用 `>` 重定向二进制 dump；先在容器内生成，再用 `docker cp` 复制到宿主机：

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$containerId = docker compose ps -q postgres
$containerBackup = "/tmp/jobpilot-pre-bge-$stamp.dump"
$hostBackup = "D:\backups\JobPilot\jobpilot-pre-bge-$stamp.dump"

New-Item -ItemType Directory -Force (Split-Path $hostBackup) | Out-Null
docker exec $containerId pg_dump -U postgres -d jobpilot -Fc -f $containerBackup
docker cp "${containerId}:$containerBackup" $hostBackup
docker exec $containerId pg_restore --list $containerBackup
Get-Item $hostBackup | Select-Object FullName, Length
Get-FileHash -Algorithm SHA256 $hostBackup
```

接受标准：`pg_dump`、`docker cp` 和 `pg_restore --list` 都成功；宿主机文件非空；SHA256 已记录。仅有文件存在不等于备份可恢复，`pg_restore --list` 是最低限度的格式校验。

本次已验证备份：

```text
D:\backups\JobPilot\jobpilot-pre-bge-20260730-174504.dump
1,988,610 bytes
SHA256 E185DD76E61A5D515390418D8C03E82C1452ED4B9B9730281F9580D0431CD638
pg_restore entries: 211
```

## 二、迁移前只读预演

在 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\reindex_knowledge_embeddings.py --pre-migration-audit
```

该模式要求数据库仍为 `vector(1536)`，不加载 BGE 模型、不调用 Embedding 接口、不更新数据库。默认只统计正文非空的 `ready` 文档。本次预期输出包括：

```text
scope=ready only, after_id=0, candidates=795, planned=795
Migration audit complete; no documents were changed.
```

只有明确想修复历史 `failed/pending/parsing` 文档时，才使用 `--include-non-ready`。不要把历史失败数据悄悄混入本次模型切换的成功率统计。

## 三、维护窗口与配置

1. 暂停文档上传、重新索引等知识库写入。
2. 临时设置 `RAG_STRATEGY=bm25`、`RAG_RERANKER_ENABLED=false` 并重启后端。
3. 启动本地双模型服务，确认 `/health` 和 `/ready` 成功。
4. 将 `backend/.env` 的 Embedding/Reranker 地址改为本地服务：

```env
EMBEDDING_BASE_URL=http://127.0.0.1:7997/v1
EMBEDDING_API_KEY=local-no-auth
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false

RERANKER_BASE_URL=http://127.0.0.1:7997/v1
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
```

## 四、执行 schema 迁移

在 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

迁移后 revision 应为 `e8f3a1c9d204`，列应为 `vector(1024)`，旧 embedding 数量应为 0。不要在模型服务未就绪时开始重建。

## 五、预检、灰度和全量重建

迁移后的 `--dry-run` 会实际请求一次 Embedding 服务，并同时验证配置维度、数据库列维度和接口返回维度：

```powershell
.\.venv\Scripts\python.exe scripts\reindex_knowledge_embeddings.py --dry-run
```

先处理少量文档验证写入链路：

```powershell
.\.venv\Scripts\python.exe scripts\reindex_knowledge_embeddings.py --limit 10
```

灰度成功后执行全量。已经完整重建的文档不再属于候选，因此从头执行不会重复处理它们：

```powershell
.\.venv\Scripts\python.exe scripts\reindex_knowledge_embeddings.py
```

脚本每处理一个文档都会输出 `last_document_id`。进程中断后可从该游标之后继续：

```powershell
.\.venv\Scripts\python.exe scripts\reindex_knowledge_embeddings.py --after-id <最后成功输出的文档ID>
```

`--after-id` 优先保证向前推进，也会跳过该 ID 之前的失败项。全量跑完后应再从 0 执行一次普通 dry-run，确认没有遗漏；若仍有候选，再从 0 重试并检查失败原因。

## 六、完成验证与策略切换

完成条件：

- 普通 `--dry-run` 输出 `candidates=0`；
- 所有原 `ready` 文档仍为 `ready`；
- `ready` 文档的 chunk 都有 1024 维 embedding；
- Vector 检索返回相关结果且不出现维度错误；
- Hybrid 检索和 Reranker 分别通过真实问题冒烟测试。

然后再逐级切换，便于定位收益和故障：

```env
# 先验证纯 Vector
RAG_STRATEGY=vector
RAG_RERANKER_ENABLED=false

# 再验证 Hybrid
RAG_STRATEGY=hybrid
RAG_RERANKER_ENABLED=false

# 最后开启精排
RAG_STRATEGY=hybrid
RAG_RERANKER_ENABLED=true
```

## 七、回退边界

接口或性能异常时，最快且不改 schema 的业务回退是：

```env
RAG_STRATEGY=bm25
RAG_RERANKER_ENABLED=false
```

如果必须恢复旧 1536 维模型，优先在独立数据库中验证备份恢复流程。`alembic downgrade d4a7c9e2b610` 只会把列改回 `vector(1536)`，同时清空当前 1024 维向量；它不会恢复旧 embedding。要恢复迁移前的精确状态，必须使用本手册第一步生成的数据库备份。

## 本次执行记录

2026-07-30 已完成 schema 迁移、10 文档灰度、全量重建和纯 Vector 验收：

| 检查项 | 执行结果 |
| --- | --- |
| 备份复核 | 1,988,610 bytes，SHA256 与迁移前记录一致 |
| 模型门禁 | `/ready` 成功；JobPilot `EmbeddingClient` 返回 1024 维 |
| Alembic | `e8f3a1c9d204 (head)` |
| pgvector 列 | `vector(1024)` |
| 文档完整性 | 文档 1094、`ready` 795、chunk 1005，均与迁移前一致 |
| 迁移后旧向量 | 0，符合迁移设计 |
| HNSW | `ix_knowledge_chunks_embedding_hnsw` 存在 |
| 灰度重建 | 10/10 成功，0 失败，最后文档 ID 29 |
| 灰度向量 | 10 个文档、15 个 chunk，全部为 1024 维 |
| 全量重建 | 剩余 785/785 成功，0 失败，最后文档 ID 1283，约 64 秒 |
| 最终向量 | 795 个 `ready` 文档、869 个 ready chunk 全部为 1024 维 |
| 最终候选 | 0 |
| 历史异常数据 | 非 ready 文档保留 54 个空向量 chunk，未混入本次迁移 |
| chunk 变化 | 总数从 1005 变为 923；由当前切片规则重建 ready 文档后产生 869 个 chunk，另保留 54 个历史异常 chunk |
| 向量召回 | 数据管道、B 轮 SaaS、个人事实三类查询 Top-1 均命中；生产 `RetrievalService` 验收通过 |
| 用户隔离 | 用户 1 查询用户 3 的 ByteDance 内容时，返回结果仍全部属于用户 1 |
| 最终业务策略 | `RAG_STRATEGY=hybrid`、Reranker 开启；等权、RRF 60、候选倍数 3 |
| 端到端模型评测 | Base + RAG / LoRA + RAG 各 200 条，400/400 成功，检索上下文 200/200 一致 |
