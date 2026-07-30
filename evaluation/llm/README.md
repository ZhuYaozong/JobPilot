# JobPilot Base / LoRA 配对评测

该工具通过同一 vLLM 进程的 `model` 字段，在完全相同的输入和生成参数下比较：

- `jobpilot-base`
- `jobpilot-lora-v1`

使用独立的 `evaluation.jsonl` 500 条数据，不复用训练、验证或普通 test 输出。

## 为什么不能只看 BLEU/ROUGE

求职回答可能存在多种正确表述，文本重合度低不一定错误。反过来，当前部分参考答案包含“反推指标、估算数字”等风险模式，过度追求参考相似度可能奖励不真实内容。因此报告同时提供：

- 字符、2-gram、4-gram 参考相似度；
- 延迟和输出 token；
- 回答新增数字声明率；
- “估算/假定/反推”等推测性数字风险率；
- 分任务类型统计；
- 分层随机人工盲评材料。

新增数字只是风险信号，不自动等价于造假，最终需要人工结合问题语境判断。

## 2026-07-30 全量结果

| 指标 | Base | LoRA |
| --- | ---: | ---: |
| 配对样本 | 500 | 500 |
| 字符 F1 | 0.2102 | 0.4464 |
| 字符 2-gram F1 | 0.0736 | 0.2054 |
| 平均延迟 | 11.756 秒 | 2.231 秒 |
| 平均输出 token | 538.11 | 95.96 |
| 新增数字样本率 | 22.2% | 79.2% |
| 推测性数字风险率 | 2.0% | 1.6% |

LoRA 的领域表达更接近参考答案且输出更短，但新增数字比例明显上升。数字指标只用于
筛查风险，不能代替事实核验；在完成 `blind_review.jsonl` 的人工盲评前，不应据此直接
宣布 LoRA 已满足生产上线标准。`results/` 被 `.gitignore` 排除，重复执行下文命令可
从同一数据和随机种子重建报告。

## 1. 静态检查

```bash
cd /home/kai/zyz/Job/jobpilot-llm/evaluation/llm
/home/kai/miniconda3/envs/j-serve/bin/python -m py_compile \
  generate_pair.py build_report.py
```

## 2. 10 条冒烟评测

```bash
/home/kai/miniconda3/envs/j-serve/bin/python generate_pair.py \
  --config config.json \
  --run-name smoke \
  --limit 10

/home/kai/miniconda3/envs/j-serve/bin/python build_report.py \
  --config config.json \
  --run-name smoke \
  --review-size 10
```

## 3. 完整 500 × 2 配对评测

建议在 tmux 中执行，避免 SSH 断开：

```bash
tmux new-session -s jobpilot_llm_eval
cd /home/kai/zyz/Job/jobpilot-llm/evaluation/llm
/home/kai/miniconda3/envs/j-serve/bin/python generate_pair.py \
  --config config.json \
  --run-name full
```

按 `Ctrl+B`、再按 `D` 退出 tmux。重新进入：

```bash
tmux attach -t jobpilot_llm_eval
```

生成结束后构建报告：

```bash
/home/kai/miniconda3/envs/j-serve/bin/python build_report.py \
  --config config.json \
  --run-name full
```

## 断点续跑

生成脚本每完成一条就立即写入 JSONL。重复执行相同命令时，会跳过已有成功记录，只重试失败记录。不要手动拼接或重排结果文件。

## 人工盲评

填写 `blind_review.jsonl` 中的：

- `preferred`：`A`、`B` 或 `TIE`；
- 任务正确性：1～5；
- 真实性：1～5；
- 清晰度：1～5；
- 备注。

评审结束前不要打开 `blind_review_key.jsonl`，否则会引入模型身份偏差。
