#!/usr/bin/env bash

# 安全地将服务启动到专属 tmux 会话，避免误用正在忙碌的 GPU。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VLLM_REQUIRE_ENV_FILE=1
# shellcheck source=common.sh
source "${DEPLOY_DIR}/common.sh"

require_value VLLM_MODEL_PATH
require_value VLLM_ADAPTER_PATH

for executable in tmux nvidia-smi ss; do
  if ! command -v "${executable}" >/dev/null 2>&1; then
    echo "错误：缺少命令 ${executable}" >&2
    exit 1
  fi
done

if tmux has-session -t "${VLLM_SESSION_NAME}" 2>/dev/null; then
  echo "服务会话 ${VLLM_SESSION_NAME} 已存在，请先运行 status_server.sh。"
  exit 0
fi

if ss -H -ltn "sport = :${VLLM_PORT}" | grep -q .; then
  echo "错误：端口 ${VLLM_PORT} 已被占用。" >&2
  exit 1
fi

used_memory_mib="$(
  nvidia-smi --id="${VLLM_PHYSICAL_GPU}" \
    --query-gpu=memory.used --format=csv,noheader,nounits | head -n 1 | tr -d '[:space:]'
)"

if [[ ! "${used_memory_mib}" =~ ^[0-9]+$ ]]; then
  echo "错误：无法读取 GPU ${VLLM_PHYSICAL_GPU} 的显存占用。" >&2
  exit 1
fi

if (( used_memory_mib > VLLM_BUSY_GPU_THRESHOLD_MIB )) && [[ "${VLLM_ALLOW_BUSY_GPU}" != "1" ]]; then
  echo "拒绝启动：GPU ${VLLM_PHYSICAL_GPU} 已占用 ${used_memory_mib} MiB。" >&2
  echo "请等待资源释放后重试。只有确认可共享时，才临时设置 VLLM_ALLOW_BUSY_GPU=1。" >&2
  exit 1
fi

mkdir -p "${VLLM_LOG_DIR}"
tmux new-session -d -s "${VLLM_SESSION_NAME}" "${DEPLOY_DIR}/run_server.sh"

echo "vLLM 已提交到 tmux 会话：${VLLM_SESSION_NAME}"
echo "启动阶段可能需要数分钟，请执行：${DEPLOY_DIR}/status_server.sh"
echo "实时日志：tail -f ${VLLM_LOG_DIR}/latest.log"
