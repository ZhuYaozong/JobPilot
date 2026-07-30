#!/usr/bin/env bash

# 同时检查进程、端口、健康接口、模型注册和物理 GPU 使用情况。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VLLM_REQUIRE_ENV_FILE=1
# shellcheck source=common.sh
source "${DEPLOY_DIR}/common.sh"

# 非交互式 SSH 不一定包含 Python 路径，显式激活推理环境。
activate_serve_env

if tmux has-session -t "${VLLM_SESSION_NAME}" 2>/dev/null; then
  echo "tmux 会话：运行中（${VLLM_SESSION_NAME}）"
else
  echo "tmux 会话：未运行（${VLLM_SESSION_NAME}）"
fi

echo "GPU ${VLLM_PHYSICAL_GPU} 状态："
nvidia-smi --id="${VLLM_PHYSICAL_GPU}" \
  --query-gpu=index,name,memory.used,memory.total,utilization.gpu \
  --format=csv,noheader

curl_auth_args
health_url="http://${VLLM_HOST}:${VLLM_PORT}/health"
models_url="http://${VLLM_HOST}:${VLLM_PORT}/v1/models"

if curl --silent --show-error --fail --max-time 5 "${CURL_AUTH_ARGS[@]}" "${health_url}" >/dev/null; then
  echo "健康检查：通过（${health_url}）"
else
  echo "健康检查：未通过。服务可能仍在加载，请查看 ${VLLM_LOG_DIR}/latest.log" >&2
  exit 1
fi

echo "已注册模型："
curl --silent --show-error --fail --max-time 10 \
  "${CURL_AUTH_ARGS[@]}" "${models_url}" | python -m json.tool
