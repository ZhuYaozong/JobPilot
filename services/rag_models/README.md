# JobPilot 本地 RAG 模型服务

该服务在一张本地 GPU 上同时加载：

- `BAAI/bge-m3`：生成 1024 维 dense embedding，供 pgvector 召回；
- `BAAI/bge-reranker-v2-m3`：对召回候选做 query-document 交叉编码评分，不写入数据库。

两个模型由同一 FastAPI 进程管理，并用推理锁串行访问 GPU，以降低 8 GiB 显存设备上的峰值占用。服务只监听 `127.0.0.1`，不会默认暴露到局域网。

## 已验证环境

本项目在 Windows、RTX 4060 Laptop GPU 和以下版本组合上通过双模型 GPU 冒烟测试：

```text
Python          j-rag Conda 环境
PyTorch         2.8.0+cu128
FlagEmbedding   1.3.5
Transformers    4.44.2
Tokenizers      0.19.1
Hugging Face Hub 0.36.2
```

不要随意把 `FlagEmbedding` 升到 1.4.0 或把 `Transformers` 升到 5.x。已经验证过的失败组合包括：

- `FlagEmbedding 1.4.0 + Transformers 5.x`：Reranker 缺少 `prepare_for_model`；
- `FlagEmbedding 1.4.0 + Transformers 4.44.2`：BGE-M3 构造时向模型传入不兼容的 `dtype` 参数。

## 安装与配置

先激活专用环境。CUDA 版 PyTorch 应单独安装，避免依赖解析时被 CPU wheel 替换：

```powershell
conda activate j-rag
python -m pip install torch==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r services/rag_models/requirements.txt
python -m pip check
```

复制本地配置；`.env` 已被 Git 忽略，不要提交真实路径：

```powershell
Copy-Item services/rag_models/.env.example services/rag_models/.env
```

若模型已经下载到 Hugging Face 默认缓存，既可以保留仓库名，也可以把下面两项改成实际 snapshot 绝对路径，从而明确使用本地文件：

```env
RAG_MODELS_EMBEDDING_MODEL=C:\Users\<用户名>\.cache\huggingface\hub\models--BAAI--bge-m3\snapshots\<revision>
RAG_MODELS_RERANKER_MODEL=C:\Users\<用户名>\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3\snapshots\<revision>
```

## 启动与健康检查

从仓库根目录启动，首次加载和预热两个模型需要等待一段时间：

```powershell
conda activate j-rag
.\services\rag_models\run.ps1
```

另开 PowerShell 检查存活与就绪状态：

```powershell
Invoke-RestMethod http://127.0.0.1:7997/health
Invoke-RestMethod http://127.0.0.1:7997/ready
```

`/health` 只说明进程存活；只有 `/ready` 返回 HTTP 200 且 `models_loaded=true`，才可以发送推理请求。服务当前还提供 `/docs` 供本地查看 OpenAPI 页面。

## API 冒烟测试

Embedding 接口与 JobPilot 的 OpenAI-compatible 客户端兼容：

```powershell
$embeddingBody = @{
    model = "BAAI/bge-m3"
    input = @("Python 后端开发", "市场营销经验")
} | ConvertTo-Json

$embedding = Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:7997/v1/embeddings `
    -ContentType "application/json" `
    -Body $embeddingBody

$embedding.data.Count
$embedding.data[0].embedding.Count
```

预期分别为 `2` 和 `1024`。Reranker 测试：

```powershell
$rerankBody = @{
    model = "BAAI/bge-reranker-v2-m3"
    query = "Python 后端岗位需要什么能力？"
    documents = @("熟悉 FastAPI 和 PostgreSQL", "擅长平面设计", "有市场投放经验")
    top_n = 2
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:7997/v1/rerank `
    -ContentType "application/json" `
    -Body $rerankBody
```

## 接入 JobPilot 后端

在 `backend/.env` 中使用同一个服务前缀。Embedding 客户端要求 API key 非空；本地服务不校验它，因此使用明确的本地占位值即可：

```env
EMBEDDING_BASE_URL=http://127.0.0.1:7997/v1
EMBEDDING_API_KEY=local-no-auth
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false

RERANKER_BASE_URL=http://127.0.0.1:7997/v1
RERANKER_API_KEY=
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
RERANKER_TIMEOUT_SECONDS=15
```

数据库仍是 `vector(1536)` 时不要开启向量写入，也不要执行知识库重建。完整的备份、迁移和重建顺序见 [BGE-M3 迁移运行手册](../../docs/rag/bge-m3-migration-runbook.md)。

## 测试

不加载真实模型的接口契约测试：

```powershell
conda activate j-rag
python -m pytest services/rag_models/tests -q -p no:cacheprovider
```

实际显存会受 Windows 图形进程和 CUDA 缓存影响。判断是否泄漏时应比较“服务启动前基线、双模型稳定值、进程退出后基线”，不要只看任务管理器中某一时刻的显存数字。
