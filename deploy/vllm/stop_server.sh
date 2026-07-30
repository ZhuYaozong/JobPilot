#!/usr/bin/env bash

# 只停止 JobPilot 自己的 tmux 会话，不使用 pkill，避免影响同服务器其他任务。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${DEPLOY_DIR}/common.sh"

if ! tmux has-session -t "${VLLM_SESSION_NAME}" 2>/dev/null; then
  echo "服务会话 ${VLLM_SESSION_NAME} 不存在，无需停止。"
  exit 0
fi

echo "向 ${VLLM_SESSION_NAME} 发送 Ctrl-C，等待 vLLM 释放显存。"
tmux send-keys -t "${VLLM_SESSION_NAME}" C-c

for _ in $(seq 1 20); do
  if ! tmux has-session -t "${VLLM_SESSION_NAME}" 2>/dev/null; then
    echo "服务已正常停止。"
    exit 0
  fi
  sleep 1
done

echo "服务未在 20 秒内退出，关闭它所属的 tmux 会话。"
tmux kill-session -t "${VLLM_SESSION_NAME}"
echo "服务已停止。"
