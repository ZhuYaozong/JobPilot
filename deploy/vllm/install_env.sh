#!/usr/bin/env bash

# 创建独立推理环境，避免 vLLM 的依赖版本影响训练环境 j-train。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${DEPLOY_DIR}/common.sh"

if [[ ! -f "${VLLM_CONDA_SH}" ]]; then
  echo "错误：找不到 Conda 初始化脚本 ${VLLM_CONDA_SH}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${VLLM_CONDA_SH}"

# 将下载缓存放在实验路径内，便于统一管理服务器空间。
mkdir -p "${VLLM_UV_CACHE_DIR}" "${VLLM_PIP_CACHE_DIR}"
export UV_CACHE_DIR="${VLLM_UV_CACHE_DIR}"
export PIP_CACHE_DIR="${VLLM_PIP_CACHE_DIR}"

if ! conda env list | awk '{print $1}' | grep -Fxq "${VLLM_CONDA_ENV}"; then
  echo "创建 Conda 环境：${VLLM_CONDA_ENV}（Python 3.11）"
  conda create -y -n "${VLLM_CONDA_ENV}" python=3.11 pip
else
  echo "Conda 环境 ${VLLM_CONDA_ENV} 已存在，继续复用。"
fi

conda activate "${VLLM_CONDA_ENV}"
python -m pip install --upgrade pip uv

if python -c 'import vllm' >/dev/null 2>&1; then
  echo "vLLM 已安装，跳过重复安装。"
else
  echo "安装 vLLM，并由安装器自动选择与当前驱动兼容的 PyTorch 后端。"
  uv pip install --python "$(command -v python)" vllm --torch-backend=auto
fi

python -m pip check
python -m pip freeze > "${DEPLOY_DIR}/requirements-serve.lock.txt"

python - <<'PY'
import sys

import torch
import vllm

print("Python:", sys.version.split()[0])
print("PyTorch:", torch.__version__)
print("PyTorch CUDA Runtime:", torch.version.cuda)
print("vLLM:", vllm.__version__)
print("CUDA 可用:", torch.cuda.is_available())
PY

echo "环境安装完成，依赖快照：${DEPLOY_DIR}/requirements-serve.lock.txt"
