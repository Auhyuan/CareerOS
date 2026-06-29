from langchain_core.tools import BaseTool

from app.server.agent.src.tools.job_tools.config import JobToolConfig, get_job_tool_config
from app.server.agent.src.tools.job_tools.job_skill import create_job_skill, search_job_skills


JOB_TOOLS: list[BaseTool] = [search_job_skills, create_job_skill]

__all__ = [
    "JOB_TOOLS",
    "JobToolConfig",
    "create_job_skill",
    "get_job_tool_config",
    "search_job_skills",
]
