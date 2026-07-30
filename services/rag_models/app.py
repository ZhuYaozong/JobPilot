"""本地 RAG 模型网关的 FastAPI 入口。"""

from contextlib import asynccontextmanager
import logging

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from services.rag_models.config import get_settings
from services.rag_models.model_runtime import ModelRuntime, ModelsNotReadyError
from services.rag_models.schemas import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    HealthResponse,
    ReadinessResponse,
    RerankRequest,
    RerankResponse,
    RerankResult,
)


logger = logging.getLogger(__name__)
settings = get_settings()
runtime = ModelRuntime(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """管理模型随服务启动和关闭的完整生命周期。"""

    if settings.load_models_on_startup:
        try:
            runtime.load()
        except Exception:
            # 保留进程和 /health，让 /ready 暴露可诊断的加载失败状态。
            logger.exception("本地 RAG 模型加载失败")
    yield
    runtime.unload()


app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    description="为 JobPilot 提供本地 Embedding 与 Rerank 推理。",
    lifespan=lifespan,
)


def _get_cuda_device_name() -> str | None:
    """读取已配置 CUDA 设备名称；CPU 配置或 CUDA 不可用时返回空。"""

    if not torch.cuda.is_available():
        return None

    configured_device = torch.device(settings.device)
    if configured_device.type != "cuda":
        return None

    device_index = configured_device.index
    if device_index is None:
        device_index = torch.cuda.current_device()
    return torch.cuda.get_device_name(device_index)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """返回进程存活状态；当前阶段不会加载模型权重。"""

    return HealthResponse(
        status="ok",
        service=settings.service_name,
        configured_device=settings.device,
        cuda_available=torch.cuda.is_available(),
        device_name=_get_cuda_device_name(),
        torch_version=torch.__version__,
        cuda_runtime=torch.version.cuda,
        models_loaded=runtime.is_loaded,
        model_error=runtime.last_error,
    )


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready() -> ReadinessResponse | JSONResponse:
    """仅当两个模型均完成预热时返回成功。"""

    response = ReadinessResponse(
        status="ready" if runtime.is_loaded else "not_ready",
        models_loaded=runtime.is_loaded,
        model_error=runtime.last_error,
    )
    if not runtime.is_loaded:
        return JSONResponse(status_code=503, content=response.model_dump())
    return response


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """使用本地 BGE-M3 返回 OpenAI-compatible dense vectors。"""

    if request.model != settings.embedding_model_name:
        raise HTTPException(
            status_code=404,
            detail=f"未知 Embedding 模型：{request.model}",
        )
    if not runtime.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=runtime.last_error or "本地 RAG 模型尚未就绪",
        )

    texts = request.normalized_input()
    try:
        result = await run_in_threadpool(runtime.embed, texts)
    except ModelsNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Embedding 推理失败")
        raise HTTPException(status_code=500, detail="Embedding 推理失败") from exc

    return EmbeddingResponse(
        model=settings.embedding_model_name,
        data=[
            EmbeddingData(index=index, embedding=vector)
            for index, vector in enumerate(result.vectors)
        ],
        usage=EmbeddingUsage(
            prompt_tokens=result.prompt_tokens,
            total_tokens=result.prompt_tokens,
        ),
    )


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest) -> RerankResponse:
    """使用本地交叉编码器对召回候选执行 Top-N 精排。"""

    if request.model != settings.reranker_model_name:
        raise HTTPException(
            status_code=404,
            detail=f"未知 Reranker 模型：{request.model}",
        )
    if not runtime.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=runtime.last_error or "本地 RAG 模型尚未就绪",
        )

    try:
        result = await run_in_threadpool(
            runtime.rerank,
            request.query,
            request.documents,
            request.top_n,
        )
    except ModelsNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reranker 推理失败")
        raise HTTPException(status_code=500, detail="Reranker 推理失败") from exc

    return RerankResponse(
        model=settings.reranker_model_name,
        results=[
            RerankResult(
                index=item.index,
                relevance_score=item.relevance_score,
            )
            for item in result.results
        ],
    )


def main() -> None:
    """以单 Worker 启动本地模型服务。"""

    import uvicorn

    uvicorn.run(
        "services.rag_models.app:app",
        host=settings.host,
        port=settings.port,
        workers=1,
    )


if __name__ == "__main__":
    main()
