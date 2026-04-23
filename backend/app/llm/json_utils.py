import json
from json import JSONDecodeError


def load_llm_json(raw_result: str) -> object:
    text = raw_result.strip()
    try:
        return json.loads(text)
    except JSONDecodeError:
        pass

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)
