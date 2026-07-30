#!/usr/bin/env bash

# 所有部署脚本共享的配置加载与校验逻辑。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${VLLM_ENV_FILE:-${DEPLOY_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
elif [[ "${VLLM_REQUIRE_ENV_FILE:-0}" == "1" ]]; then
  echo "错误：未找到配置文件 ${ENV_FILE}" >&2
  echo "请先执行：cp ${DEPLOY_DIR}/env.example ${DEPLOY_DIR}/.env" >&2
  exit 1
fi

: "${VLLM_CONDA_ENV:=j-serve}"
: "${VLLM_CONDA_SH:=/home/kai/miniconda3/etc/profile.d/conda.sh}"
: "${VLLM_UV_CACHE_DIR:=/home/kai/zyz/Job/.cache/uv}"
: "${VLLM_PIP_CACHE_DIR:=/home/kai/zyz/Job/.cache/pip}"
: "${VLLM_BASE_MODEL_NAME:=jobpilot-base}"
: "${VLLM_LORA_MODEL_NAME:=jobpilot-lora-v1}"
: "${VLLM_HOST:=127.0.0.1}"
: "${VLLM_PORT:=8000}"
: "${VLLM_API_KEY:=}"
: "${VLLM_PHYSICAL_GPU:=1}"
: "${VLLM_MAX_MODEL_LEN:=16384}"
: "${VLLM_GPU_MEMORY_UTILIZATION:=0.90}"
: "${VLLM_MAX_NUM_SEQS:=4}"
: "${VLLM_MAX_LORA_RANK:=16}"
: "${VLLM_MAX_LORAS:=1}"
: "${VLLM_SESSION_NAME:=jobpilot_vllm}"
: "${VLLM_BUSY_GPU_THRESHOLD_MIB:=512}"
: "${VLLM_ALLOW_BUSY_GPU:=0}"
: "${VLLM_LOG_DIR:=${DEPLOY_DIR}/logs}"

export DEPLOY_DIR ENV_FILE
export VLLM_CONDA_ENV VLLM_CONDA_SH VLLM_UV_CACHE_DIR VLLM_PIP_CACHE_DIR
export VLLM_BASE_MODEL_NAME VLLM_LORA_MODEL_NAME
export VLLM_HOST VLLM_PORT VLLM_API_KEY VLLM_PHYSICAL_GPU
export VLLM_MAX_MODEL_LEN VLLM_GPU_MEMORY_UTILIZATION VLLM_MAX_NUM_SEQS
export VLLM_MAX_LORA_RANK VLLM_MAX_LORAS VLLM_SESSION_NAME
export VLLM_BUSY_GPU_THRESHOLD_MIB VLLM_ALLOW_BUSY_GPU VLLM_LOG_DIR

require_value() {
  local variable_name="$1"
  if [[ -z "${!variable_name:-}" ]]; then
    echo "错误：配置项 ${variable_name} 不能为空。" >&2
    exit 1
  fi
}

activate_serve_env() {
  if [[ ! -f "${VLLM_CONDA_SH}" ]]; then
    echo "错误：找不到 Conda 初始化脚本 ${VLLM_CONDA_SH}" >&2
    exit 1
  fi

  # shellcheck disable=SC1090
  source "${VLLM_CONDA_SH}"
  conda activate "${VLLM_CONDA_ENV}"
}

curl_auth_args() {
  CURL_AUTH_ARGS=()
  if [[ -n "${VLLM_API_KEY}" ]]; then
    CURL_AUTH_ARGS=(-H "Authorization: Bearer ${VLLM_API_KEY}")
  fi
}
