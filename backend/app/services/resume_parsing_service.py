from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.resume import Resume
from app.schemas.resume_parsing import ResumeParsingResult


def build_resume_parsing_prompt(resume: Resume) -> str:
    return f"""You are a resume parser.
Extract structured information from the following resume.
Return JSON only, with this shape:
{{
  "summary": string or null,
  "skills": string[],
  "experiences": string[],
  "projects": string[],
  "education": string[],
  "target_roles": string[],
  "years_of_experience": string or null
}}

Resume title: {resume.title}
Resume text:
{resume.raw_text}
"""


async def parse_resume(
    db: AsyncSession,
    resume: Resume,
    llm_client: LLMClient | None = None,
) -> Resume:
    if not resume.raw_text or not resume.raw_text.strip():
        raise HTTPException(status_code=400, detail="Resume raw text is empty")

    client = llm_client or LLMClient()
    prompt = build_resume_parsing_prompt(resume)

    try:
        raw_result = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        parsed_data = load_llm_json(raw_result)
        result = ResumeParsingResult.model_validate(parsed_data)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM response is not valid JSON") from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match resume parsing schema",
        ) from exc

    resume.parsed_json = result.model_dump()
    resume.parse_status = "parsed"
    await db.commit()
    await db.refresh(resume)
    return resume
