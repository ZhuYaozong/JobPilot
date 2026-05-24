"""Agent 工具注册表。

这是 Agent 可调用工具的唯一注册表。workflow 只通过工具名查这里，
不要在 prompt 或 workflow 里手写单独的工具分支，避免注册表和提示词漂移。

workflow 会用 ``state["tool_name"]`` 从这个字典里取工具类。新增工具时，只需要在
``tools/`` 下新增模块，再把类加入这个注册表。

工具大致分六类：

- **列表 / 读工具**(``list_user_*``、``read_resume``、``read_job_posting``、
  ``list_generated_artifacts``)：便宜、无 LLM、无副作用。list 拿 id,read 拿细节。
- **检索工具**(``search_knowledge``)：对用户上传的知识库内容做语义检索，每次调用会
  发起一次 embedding 请求。
- **解析工具**(``parse_resume``、``parse_job_posting``)：对已落库但未解析的简历 /
  岗位触发 LLM 结构化抽取,把 parse_status 从 pending 升级到 parsed。
- **动作工具**(``analyze_match``、``generate_cover_letter``、
  ``generate_interview_prep``、``generate_tailored_resume``)：调用业务 service，
  通常耗时数秒并写入数据库，一轮对话里一般只调用一次。
- **草稿 / 创建工具**(``draft_job``、``draft_resume``、``create_job``、
  ``create_resume``)：用于"用户在对话里贴 JD/简历文本 → Agent 起草 →
  用户确认 → 落库"的两步流程。draft_* 调 LLM 但不写库；create_* 只写库不调 LLM。
- **投递 / 知识写入工具**(``create_application``、``update_application_stage``、
  ``add_knowledge_text``)：写业务记录。``add_knowledge_text`` **只在用户明确要求保存
  时调用**,不要把用户随手粘贴的内容自动入库,具体规则见工具 description。
"""

from app.agent.tool_adapter import BaseTool
from app.agent.tools.add_knowledge_text_tool import AddKnowledgeTextTool
from app.agent.tools.cover_letter_tool import CoverLetterTool
from app.agent.tools.create_application_tool import CreateApplicationTool
from app.agent.tools.create_job_tool import CreateJobTool
from app.agent.tools.create_resume_tool import CreateResumeTool
from app.agent.tools.draft_job_tool import DraftJobTool
from app.agent.tools.draft_resume_tool import DraftResumeTool
from app.agent.tools.interview_prep_tool import InterviewPrepTool
from app.agent.tools.list_generated_artifacts_tool import ListGeneratedArtifactsTool
from app.agent.tools.list_user_applications_tool import ListUserApplicationsTool
from app.agent.tools.list_user_jobs_tool import ListUserJobsTool
from app.agent.tools.list_user_resumes_tool import ListUserResumesTool
from app.agent.tools.match_analysis_tool import MatchAnalysisTool
from app.agent.tools.parse_job_posting_tool import ParseJobPostingTool
from app.agent.tools.parse_resume_tool import ParseResumeTool
from app.agent.tools.read_job_posting_tool import ReadJobPostingTool
from app.agent.tools.read_resume_tool import ReadResumeTool
from app.agent.tools.search_knowledge_tool import SearchKnowledgeTool
from app.agent.tools.tailored_resume_tool import TailoredResumeTool
from app.agent.tools.update_application_stage_tool import UpdateApplicationStageTool

# key 必须等于工具暴露给 LLM 的技术名；前端展示中文名由 labels 映射负责。
TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    ListUserJobsTool.name: ListUserJobsTool,
    ListUserResumesTool.name: ListUserResumesTool,
    ListUserApplicationsTool.name: ListUserApplicationsTool,
    SearchKnowledgeTool.name: SearchKnowledgeTool,
    MatchAnalysisTool.name: MatchAnalysisTool,
    CoverLetterTool.name: CoverLetterTool,
    InterviewPrepTool.name: InterviewPrepTool,
    TailoredResumeTool.name: TailoredResumeTool,
    DraftJobTool.name: DraftJobTool,
    DraftResumeTool.name: DraftResumeTool,
    CreateJobTool.name: CreateJobTool,
    CreateResumeTool.name: CreateResumeTool,
    ReadResumeTool.name: ReadResumeTool,
    ReadJobPostingTool.name: ReadJobPostingTool,
    ParseResumeTool.name: ParseResumeTool,
    ParseJobPostingTool.name: ParseJobPostingTool,
    AddKnowledgeTextTool.name: AddKnowledgeTextTool,
    CreateApplicationTool.name: CreateApplicationTool,
    UpdateApplicationStageTool.name: UpdateApplicationStageTool,
    ListGeneratedArtifactsTool.name: ListGeneratedArtifactsTool,
}

__all__ = [
    "TOOL_REGISTRY",
    "AddKnowledgeTextTool",
    "CoverLetterTool",
    "CreateApplicationTool",
    "CreateJobTool",
    "CreateResumeTool",
    "DraftJobTool",
    "DraftResumeTool",
    "InterviewPrepTool",
    "ListGeneratedArtifactsTool",
    "ListUserApplicationsTool",
    "ListUserJobsTool",
    "ListUserResumesTool",
    "MatchAnalysisTool",
    "ParseJobPostingTool",
    "ParseResumeTool",
    "ReadJobPostingTool",
    "ReadResumeTool",
    "SearchKnowledgeTool",
    "TailoredResumeTool",
    "UpdateApplicationStageTool",
]
