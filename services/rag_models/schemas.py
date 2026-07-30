"""本地 RAG 模型网关的 API 数据结构。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class HealthResponse(BaseModel):
    """服务存活状态与本地 CUDA 基线信息。"""

    status: Literal["ok"]
    service: str
    configured_device: str
    cuda_available: bool
    device_name: str | None
    torch_version: str
    cuda_runtime: str | None
    models_loaded: bool
    model_error: str | None


class ReadinessResponse(BaseModel):
    """模型是否已经可以处理推理请求。"""

    status: Literal["ready", "not_ready"]
    models_loaded: bool
    model_error: str | None


class EmbeddingRequest(BaseModel):
    """OpenAI-compatible Embedding 请求。"""

    model: str
    input: str | list[str]
    dimensions: Literal[1024] | None = None
    encoding_format: Literal["float"] = "float"

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """模型名不能为空。"""

        if not value.strip():
            raise ValueError("model 不能为空")
        return value

    @field_validator("input")
    @classmethod
    def validate_input(cls, value: str | list[str]) -> str | list[str]:
        """限制单次批量规模，并拒绝空文本。"""

        texts = [value] if isinstance(value, str) else value
        if not texts:
            raise ValueError("input 不能为空")
        if len(texts) > 256:
            raise ValueError("单次最多处理 256 条文本")
        if any(not text.strip() for text in texts):
            raise ValueError("input 不能包含空文本")
        return value

    def normalized_input(self) -> list[str]:
        """统一转换成保持原顺序的文本列表。"""

        return [self.input] if isinstance(self.input, str) else self.input


class EmbeddingData(BaseModel):
    """单条 OpenAI-compatible Embedding 数据。"""

    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    """本次向量化实际消耗的输入 token 数。"""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """OpenAI-compatible Embedding 响应。"""

    object: Literal["list"] = "list"
    model: str
    data: list[EmbeddingData]
    usage: EmbeddingUsage


class RerankRequest(BaseModel):
    """通用 POST /rerank 请求。"""

    model: str
    query: str
    documents: list[str]
    top_n: int = Field(ge=1, le=256)

    @field_validator("model", "query")
    @classmethod
    def validate_non_empty_string(cls, value: str) -> str:
        """模型名和查询都必须包含有效文本。"""

        if not value.strip():
            raise ValueError("字段不能为空")
        return value

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, value: list[str]) -> list[str]:
        """限制候选规模，并拒绝空候选正文。"""

        if not value:
            raise ValueError("documents 不能为空")
        if len(value) > 256:
            raise ValueError("单次最多处理 256 篇候选文档")
        if any(not document.strip() for document in value):
            raise ValueError("documents 不能包含空文本")
        return value

    @model_validator(mode="after")
    def validate_top_n(self) -> "RerankRequest":
        """Top-N 不能超过候选数量。"""

        if self.top_n > len(self.documents):
            raise ValueError("top_n 不能超过 documents 数量")
        return self


class RerankResult(BaseModel):
    """单个候选的原索引与相关性分数。"""

    index: int
    relevance_score: float


class RerankResponse(BaseModel):
    """按相关性降序排列的 Reranker 响应。"""

    model: str
    results: list[RerankResult]
