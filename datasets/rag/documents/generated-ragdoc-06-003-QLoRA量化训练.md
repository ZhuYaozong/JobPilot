# QLoRA量化训练

## 概念

QLoRA是一种结合了4-bit NormalFloat（NF4）量化和低秩适配（LoRA）的高效微调方法。它通过将预训练模型的权重以4-bit精度量化存储，并在前向传播时动态反量化到计算精度，同时利用LoRA注入可训练的低秩矩阵，从而在保持性能的同时大幅降低显存占用和存储开销。QLoRA使得在单张消费级GPU（如RTX 3090）上微调65B模型成为可能。

## 原理

QLoRA的核心原理包括两点：
1. **NF4量化**：使用信息理论上最优的4-bit数据类型——NormalFloat（NF），它适配于正态分布的权重，在每个块（例如64个参数）内独立进行归一化和量化，减少量化损失。同时采用**双重量化**：对量化常数再进行一次8-bit量化，进一步节省显存。
2. **LoRA低秩适配**：冻结量化后的预训练权重，在模型特定层（如注意力层）旁路插入可训练的低秩分解矩阵（秩r远小于隐藏层维度），只更新这些矩阵。

训练时，量化权重参与前向计算，但反向传播梯度只更新LoRA参数。NF4的量化误差通过**分块缩放**和**双重量化**得到控制，使得微调性能接近全精度LoRA。

## 实践案例

### 架构流程
以微调一个7B参数的LLaMA模型为例：
1. 加载4-bit NF4量化后的基座模型（使用bitsandbytes库）。
2. 配置LoRA参数，注入目标模块（如q_proj, v_proj）。
3. 准备数据集（如Alpaca指令数据），构造输入格式。
4. 设置训练参数（batch size、学习率等），启动训练。
5. 保存LoRA适配器权重（量化基座权重不变）。
6. 推理时合并权重或动态加载LoRA。

### 关键参数
```python
from transformers import BitsAndBytesConfig, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

# 量化配置
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)

# LoRA配置
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# 训练超参
per_device_train_batch_size = 2
gradient_accumulation_steps = 4
learning_rate = 2e-4
num_train_epochs = 3
```

### 异常处理
- **OOM（显存不足）**：降低`per_device_train_batch_size`或`gradient_accumulation_steps`；启用`gradient_checkpointing`；减少LoRA秩r或目标模块数。
- **NaN损失**：降低学习率；检查数据中是否存在特殊标记；确保使用`bnb_4bit_compute_dtype`与模型计算精度一致。
- **加载失败**：确认transformers、bitsandbytes、peft版本兼容（建议transformers≥4.30.0，bitsandbytes≥0.39.0）。

### 监控指标
- **训练损失（loss）**：下降曲线是否平滑。
- **验证困惑度（perplexity）**：在保留集上评估生成质量。
- **显存占用**：通过`nvidia-smi`或`torch.cuda.max_memory_allocated`监控。
- **吞吐量（tokens/sec）**：衡量训练速度。

### 方案取舍
| 对比项 | QLoRA (4-bit) | LoRA (16-bit) | 全参微调 |
|-------|---------------|---------------|----------|
| 显存占用 | ~6GB (7B) | ~16GB | ~56GB |
| 训练速度 | 较慢（量化开销） | 较快 | 最快 |
| 微调精度 | 接近LoRA | 高 | 最高 |
| 适用场景 | 显存受限 | 显存充裕 | 资源充足 |

若显存极度紧张，优先选择QLoRA；若任务对精度要求极高且拥有多卡，可考虑全参微调。
