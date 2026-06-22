import json
import re
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.server.job.src.clients import CapabilityAgentClient
from app.server.job.src.models.job_model import JobMarketProfile
from app.server.job.src.repository.job_repository import JobRepository
from app.server.job.src.schemas.job_profile import (
    GeneratedJobProfile,
    TemporaryJobProfileGenerateRequest,
)


JOB_PROFILE_SYSTEM_PROMPT = """
你是岗位画像提炼 Agent。你的任务是只根据用户提供的岗位材料，生成结构化岗位画像。

必须遵守以下规则：
1. 只能使用用户提供的材料，不得使用外部知识补充或推测。
2. job_name 必须生成。没有明确岗位名称时，根据职责、技能和工作内容提炼最贴切的名称；
   完全无法判断时返回“未明确岗位”。
3. 输入中没有明确依据的文本字段返回 null，列表字段返回 []。
4. 不得推测学历、经验、证书、技能等级、岗位职责或工具框架。
5. 删除公司介绍、福利待遇、公司资质、联系方式等与岗位画像无关的内容。
6. 必备技能和加分技能不得重复。
7. 只输出一个合法 JSON 对象，不要输出 Markdown、代码围栏、解释或其他文字。

JSON 结构必须严格如下：
{
  "job_name": "字符串，必填",
  "job_overview": "字符串或 null",
  "responsibilities": [
    {
      "name": "字符串或 null",
      "description": "字符串或 null"
    }
  ],
  "required_skills": [
    {
      "name": "字符串，必填",
      "category": "字符串或 null",
      "level": "了解、熟悉、熟练掌握、能够独立应用之一，或 null",
      "requirement": "字符串或 null",
      "knowledge_points": ["字符串"],
      "tools": ["字符串"]
    }
  ],
  "preferred_skills": [
    {
      "name": "字符串，必填",
      "category": "字符串或 null",
      "requirement": "字符串或 null",
      "tools": ["字符串"]
    }
  ],
  "education_requirement": "字符串或 null",
  "experience_requirement": "字符串或 null",
  "certificate_requirement": "字符串或 null"
}
""".strip()


class JobProfileService:
    """岗位画像服务，负责临时画像生成、校验、保存和详情查询。"""

    def __init__(
        self,
        repository: JobRepository | None = None,
        capability_agent_client: CapabilityAgentClient | None = None,
    ):
        """
        初始化岗位画像服务。
        Args:
            repository: 岗位库数据访问对象。
            capability_agent_client: 能力层通用 Agent 客户端。
        """
        self.repository = repository or JobRepository()
        self.capability_agent_client = capability_agent_client or CapabilityAgentClient()

    def generate_temporary_profile(
        self,
        db: Session,
        request: TemporaryJobProfileGenerateRequest,
    ) -> JobMarketProfile:
        """
        根据用户提交的岗位文本生成并保存临时岗位画像。
        Args:
            db: 数据库会话。
            request: 用户临时岗位画像生成请求。
        Returns:
            已保存的临时岗位画像。
        Raises:
            BusinessException: 功能未开放、Agent 调用失败或输出校验失败。
        """
        if request.use_system_job_data:
            raise BusinessException(code=400, msg="参考系统岗位数据功能暂未开放")

        cleaned_job_text = self._clean_job_text(request.job_text)
        agent_result = self._call_profile_agent(cleaned_job_text)

        try:
            generated_profile = self._validate_generated_profile(agent_result)
        except (ValueError, ValidationError) as first_error:
            # Agent 可能返回带代码围栏的内容、缺少字段或类型不匹配。
            # 第一版只允许修复一次，避免无限调用模型并产生不可控成本。
            repaired_result = self._repair_agent_output(
                cleaned_job_text=cleaned_job_text,
                agent_result=agent_result,
                validation_error=str(first_error),
            )
            try:
                generated_profile = self._validate_generated_profile(repaired_result)
            except (ValueError, ValidationError) as second_error:
                raise BusinessException(
                    code=422,
                    msg=f"岗位画像生成结果格式不正确: {second_error}",
                ) from second_error

        profile = JobMarketProfile(
            user_id=request.user_id,
            profile_type="temporary",
            job_name=generated_profile.job_name,
            job_overview=generated_profile.job_overview,
            responsibilities=[item.model_dump() for item in generated_profile.responsibilities],
            required_skills=[item.model_dump() for item in generated_profile.required_skills],
            preferred_skills=[item.model_dump() for item in generated_profile.preferred_skills],
            education_requirement=generated_profile.education_requirement,
            experience_requirement=generated_profile.experience_requirement,
            certificate_requirement=generated_profile.certificate_requirement,
        )
        return self.repository.create_profile(profile, db)

    def get_profile_detail(self, db: Session, profile_id: int) -> JobMarketProfile | None:
        """
        根据画像 ID 查询岗位画像详情。
        Args:
            db: 数据库会话。
            profile_id: 岗位画像 ID。
        Returns:
            岗位画像详情；不存在时返回 None。
        """
        return self.repository.get_profile_by_id(profile_id, db)

    def _clean_job_text(self, job_text: str) -> str:
        """
        清理用户岗位文本中的多余空白。
        Args:
            job_text: 用户提交的岗位相关文本。
        Returns:
            清理后的岗位文本。
        """
        normalized_text = job_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        normalized_text = re.sub(r"[ \t]+", " ", normalized_text)
        normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text)
        if not normalized_text:
            raise BusinessException(code=422, msg="job_text 不能为空")
        return normalized_text

    def _call_profile_agent(self, cleaned_job_text: str) -> dict[str, Any]:
        """
        调用能力层 Agent 生成岗位画像。
        Args:
            cleaned_job_text: 清理后的岗位文本。
        Returns:
            能力层 Agent 运行结果。
        """
        payload = {
            "query": f"请根据以下岗位材料生成岗位画像：\n\n{cleaned_job_text}",
            "system_prompt": JOB_PROFILE_SYSTEM_PROMPT,
            "inputs": {},
            "files": [],
            "tools": [],
            "optional_features": {
                "long_term_memory_enabled": False,
                "conversation_context_enabled": False,
                "checkpoint_enabled": True,
                "deferred_tool_filter_enabled": False,
            },
            "runtime_options": {
                "temperature": 0.1,
                "timeout_seconds": 60,
                "max_retries": 2,
            },
        }
        try:
            return self.capability_agent_client.run_agent(payload)
        except RuntimeError as error:
            raise BusinessException(code=502, msg=str(error)) from error

    def _repair_agent_output(
        self,
        *,
        cleaned_job_text: str,
        agent_result: dict[str, Any],
        validation_error: str,
    ) -> dict[str, Any]:
        """
        请求 Agent 根据校验错误修复一次岗位画像输出。
        Args:
            cleaned_job_text: 原始岗位材料。
            agent_result: 第一次 Agent 运行结果。
            validation_error: 第一次输出的校验错误。
        Returns:
            修复后的 Agent 运行结果。
        """
        original_output = agent_result.get("structured_output") or agent_result.get("answer") or ""
        payload = {
            "query": (
                "请修复下面的岗位画像输出，使其严格符合系统提示词中的 JSON 结构。"
                "只能根据原始岗位材料修复，不得补充新事实。\n\n"
                f"原始岗位材料：\n{cleaned_job_text}\n\n"
                f"待修复输出：\n{original_output}\n\n"
                f"校验错误：\n{validation_error}"
            ),
            "system_prompt": JOB_PROFILE_SYSTEM_PROMPT,
            "inputs": {},
            "files": [],
            "tools": [],
            "optional_features": {
                "long_term_memory_enabled": False,
                "conversation_context_enabled": False,
                "checkpoint_enabled": True,
                "deferred_tool_filter_enabled": False,
            },
            "runtime_options": {
                "temperature": 0,
                "timeout_seconds": 60,
                "max_retries": 1,
            },
        }
        try:
            return self.capability_agent_client.run_agent(payload)
        except RuntimeError as error:
            raise BusinessException(code=502, msg=str(error)) from error

    def _validate_agent_result(self, agent_result: dict[str, Any]) -> GeneratedJobProfile:
        """
        提取并校验能力层 Agent 返回的岗位画像。
        Args:
            agent_result: 能力层 Agent 运行结果。
        Returns:
            通过 Pydantic 校验的岗位画像。
        Raises:
            ValueError: 响应中不存在可解析的 JSON。
            ValidationError: JSON 不符合岗位画像 Schema。
        """
        structured_output = agent_result.get("structured_output")
        if isinstance(structured_output, dict):
            profile_data = structured_output
        else:
            answer = agent_result.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Agent 没有返回岗位画像内容")
            profile_data = self._extract_json_object(answer)

        return GeneratedJobProfile.model_validate(profile_data)

    def _validate_generated_profile(self, agent_result: dict[str, Any]) -> GeneratedJobProfile:
        """
        完成岗位画像结构校验和跨字段业务规则校验。
        Args:
            agent_result: 能力层 Agent 运行结果。
        Returns:
            完整通过校验的岗位画像。
        Raises:
            ValueError: JSON 提取失败或业务规则不满足。
            ValidationError: JSON 不符合岗位画像 Schema。
        """
        profile = self._validate_agent_result(agent_result)
        self._validate_profile_business_rules(profile)
        return profile

    def _extract_json_object(self, answer: str) -> dict[str, Any]:
        """
        从 Agent 文本回答中提取 JSON 对象。
        Args:
            answer: Agent 返回的文本。
        Returns:
            解析后的 JSON 字典。
        Raises:
            ValueError: 文本中不存在合法 JSON 对象。
        """
        cleaned_answer = answer.strip()
        fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned_answer, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            cleaned_answer = fence_match.group(1).strip()

        try:
            parsed = json.loads(cleaned_answer)
        except json.JSONDecodeError:
            start_index = cleaned_answer.find("{")
            end_index = cleaned_answer.rfind("}")
            if start_index < 0 or end_index <= start_index:
                raise ValueError("Agent 输出中未找到 JSON 对象")
            try:
                parsed = json.loads(cleaned_answer[start_index : end_index + 1])
            except json.JSONDecodeError as error:
                raise ValueError(f"Agent 输出 JSON 解析失败: {error.msg}") from error

        if not isinstance(parsed, dict):
            raise ValueError("Agent 输出必须是 JSON 对象")
        return parsed

    def _validate_profile_business_rules(self, profile: GeneratedJobProfile) -> None:
        """
        校验岗位画像中跨字段的业务规则。
        Args:
            profile: 通过结构校验的岗位画像。
        Raises:
            ValueError: 技能重复或必备、加分技能发生冲突。
        """
        required_names = [item.name.strip().casefold() for item in profile.required_skills]
        preferred_names = [item.name.strip().casefold() for item in profile.preferred_skills]

        if len(required_names) != len(set(required_names)):
            raise ValueError("岗位画像中的必备技能存在重复")
        if len(preferred_names) != len(set(preferred_names)):
            raise ValueError("岗位画像中的加分技能存在重复")

        overlapping_names = set(required_names) & set(preferred_names)
        if overlapping_names:
            raise ValueError("同一技能不能同时属于必备技能和加分技能")
