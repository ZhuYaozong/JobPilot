"""LLM JSON 输出清洗工具。

很多模型会把 JSON 包进 Markdown code fence。业务层仍要求最终进入 Pydantic
校验的是纯 JSON，因此这里集中处理“裸 JSON”和“```json ... ```”两类形状。
"""

import json
from json import JSONDecodeError


def load_llm_json(raw_result: str) -> object:
    """解析模型返回的 JSON。

    先尝试直接解析；失败后再剥掉 Markdown code fence。这样正常 JSON 走最快路径，
    只有模型多包了一层代码块时才进入兼容逻辑。
    """
    text = raw_result.strip()
    try:
        return json.loads(text)
    except JSONDecodeError:
        pass

    if text.startswith("```"):
        # 支持 ```json / ```JSON / ``` 这类首行标记；末尾只接受单独一行 fence。
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)
