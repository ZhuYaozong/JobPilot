#!/usr/bin/env bash

# 前台运行 vLLM。日常启动请使用 start_server.sh 交给 tmux 管理。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VLLM_REQUIRE_ENV_FILE=1
# shellcheck source=common.sh
source "${DEPLOY_DIR}/common.sh"

require_value VLLM_MODEL_PATH
require_value VLLM_ADAPTER_PATH
activate_serve_env

python "${DEPLOY_DIR}/check_artifacts.py"

mkdir -p "${VLLM_LOG_DIR}"
VLLM_LOG_FILE="${VLLM_LOG_DIR}/vllm-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "${VLLM_LOG_FILE}" "${VLLM_LOG_DIR}/latest.log"
exec > >(tee -a "${VLLM_LOG_FILE}") 2>&1

export CUDA_VISIBLE_DEVICES="${VLLM_PHYSICAL_GPU}"
export HF_HOME="${HF_HOME:-/home/kai/zyz/Over/hf_home}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export TOKENIZERS_PARALLELISM=false

command=(
  vllm serve "${VLLM_MODEL_PATH}"
  --served-model-name "${VLLM_BASE_MODEL_NAME}"
  --host "${VLLM_HOST}"
  --port "${VLLM_PORT}"
  --dtype bfloat16
  --tensor-parallel-size 1
  --max-model-len "${VLLM_MAX_MODEL_LEN}"
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION}"
  --max-num-seqs "${VLLM_MAX_NUM_SEQS}"
  --enable-prefix-caching
  --generation-config vllm
  --enable-lora
  --max-loras "${VLLM_MAX_LORAS}"
  --max-lora-rank "${VLLM_MAX_LORA_RANK}"
  --lora-modules "${VLLM_LORA_MODEL_NAME}=${VLLM_ADAPTER_PATH}"
  --uvicorn-log-level info
)

if [[ -n "${VLLM_API_KEY}" ]]; then
  command+=(--api-key "${VLLM_API_KEY}")
fi

echo "启动模型：${VLLM_BASE_MODEL_NAME} + ${VLLM_LORA_MODEL_NAME}"
echo "物理 GPU：${VLLM_PHYSICAL_GPU}；vLLM 内部逻辑设备：cuda:0"
echo "服务地址：http://${VLLM_HOST}:${VLLM_PORT}/v1"
echo "日志文件：${VLLM_LOG_FILE}"

# vLLM 会扫描所有 VLLM_ 前缀变量。命令参数已经展开后，移除本项目自定义变量，
# 只保留官方支持的 VLLM_USE_FLASHINFER_SAMPLER，避免产生未知变量告警。
unset VLLM_ENV_FILE VLLM_REQUIRE_ENV_FILE
unset VLLM_CONDA_ENV VLLM_CONDA_SH VLLM_UV_CACHE_DIR VLLM_PIP_CACHE_DIR
unset VLLM_MODEL_PATH VLLM_ADAPTER_PATH
unset VLLM_BASE_MODEL_NAME VLLM_LORA_MODEL_NAME
unset VLLM_HOST VLLM_PORT VLLM_API_KEY VLLM_PHYSICAL_GPU
unset VLLM_MAX_MODEL_LEN VLLM_GPU_MEMORY_UTILIZATION VLLM_MAX_NUM_SEQS
unset VLLM_MAX_LORA_RANK VLLM_MAX_LORAS
unset VLLM_SESSION_NAME VLLM_BUSY_GPU_THRESHOLD_MIB VLLM_ALLOW_BUSY_GPU
unset VLLM_LOG_DIR

exec "${command[@]}"
