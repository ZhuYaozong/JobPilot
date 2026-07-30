# JobPilot vLLM 部署

本目录用一个 vLLM 进程同时提供两个 OpenAI-compatible 模型名：

- `jobpilot-base`：Qwen2.5-7B-Instruct 原始模型。
- `jobpilot-lora-v1`：同一 Base 权重上动态加载 JobPilot LoRA adapter。

动态 LoRA 的好处是 Base 权重只占一份显存，既能供 Agent 使用，也能支持后续 Base/LoRA 对照实验。服务只监听服务器 `127.0.0.1:8000`，通过 SSH 隧道访问，不直接暴露公网端口。

## 1. 准备配置

```bash
cd /home/kai/zyz/Job/jobpilot-llm/deploy/vllm
cp env.example .env
chmod +x ./*.sh
```

检查 `.env` 中模型与 adapter 路径。默认使用服务器第二张物理显卡（编号 1）。

## 2. 安装独立推理环境

为什么单独使用 `j-serve`：vLLM 会约束 PyTorch、CUDA 扩展等依赖。与 `j-train` 隔离后，不会破坏已经验证通过的 LLaMA-Factory 训练环境。

```bash
./install_env.sh
```

脚本会创建 Python 3.11 环境、安装 vLLM、执行依赖一致性检查，并生成 `requirements-serve.lock.txt` 作为可追溯快照。

## 3. 零显存静态检查

```bash
set -a
source .env
set +a
/home/kai/miniconda3/bin/python check_artifacts.py
```

该检查验证模型架构、上下文上限、tokenizer、LoRA 类型、rank、权重大小与 SHA256，不会加载模型或占用 GPU。

## 4. 启动与观察

等第二张 GPU 释放后执行：

```bash
./start_server.sh
./status_server.sh
tail -f logs/latest.log
```

安全保护默认在 GPU 已占用超过 512 MiB 时拒绝启动。不要为了抢占共享资源随意绕过；只有明确确认可共享时，才临时设置 `VLLM_ALLOW_BUSY_GPU=1`。

核心参数：

- `--dtype bfloat16`：3090 支持 BF16，7B Base 权重约占 14 GiB。
- `--max-model-len 16384`：保留 Agent/RAG 所需的较长上下文；KV Cache 会随上下文和并发增加。
- `--max-num-seqs 4`：单卡优先稳定性，限制同时在途的序列数。
- `--gpu-memory-utilization 0.90`：给 CUDA 上下文和运行时保留余量。
- `--enable-lora`：请求使用 `jobpilot-lora-v1` 时动态应用 adapter。
- `--generation-config vllm`：避免模型仓库中的生成参数静默覆盖 API 请求。
- `VLLM_USE_FLASHINFER_SAMPLER=0`：系统 nvcc 为 CUDA 11.8，关闭需要现场编译的 FlashInfer sampler；注意力计算仍使用 FlashAttention 2。

## 5. API 验证

在服务器本机测试 Base 与 LoRA：

```bash
python test_api.py
python test_api.py --stream
```

Windows 本地建立隧道：

```powershell
ssh -o ExitOnForwardFailure=yes -N -L 127.0.0.1:18000:127.0.0.1:8000 30493090
```

另开 PowerShell，在项目目录测试：

```powershell
python .\deploy\vllm\test_api.py --base-url http://127.0.0.1:18000/v1
```

如果 `.env` 设置了 `VLLM_API_KEY`，测试时也需传入同一个 key，或让测试进程读取该环境变量。

## 6. 接入 JobPilot

JobPilot 已使用 OpenAI-compatible `/chat/completions`。本地后端只需配置：

```dotenv
LLM_BASE_URL=http://127.0.0.1:18000/v1
LLM_API_KEY=EMPTY
LLM_MODEL_NAME=jobpilot-lora-v1
```

当 vLLM 配置了 API key 时，将 `EMPTY` 替换为相同值。切换 `LLM_MODEL_NAME=jobpilot-base` 即可进行 Base 对照，不需要修改 LangGraph 或 RAG 代码。

## 7. 停止服务

```bash
./stop_server.sh
```

脚本只操作名为 `jobpilot_vllm` 的 tmux 会话，不会使用 `pkill`，因此不会误停其他训练或推理任务。

## 参考

- [vLLM GPU 安装](https://docs.vllm.ai/en/stable/getting_started/installation/gpu.html)
- [OpenAI-compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/)
- [vLLM LoRA](https://docs.vllm.ai/en/stable/features/lora/)
