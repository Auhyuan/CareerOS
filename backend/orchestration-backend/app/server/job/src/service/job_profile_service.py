import json
import re
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.server.job.src.config.job_config import JOB_DEFAULT_PAGE, JOB_DEFAULT_PAGE_SIZE, JOB_MAX_PAGE_SIZE
from app.server.job.src.clients import CapabilityAgentClient
from app.server.job.src.models.job_model import JobMarketProfile
from app.server.job.src.repository.job_repository import JobRepository
from app.server.job.src.schemas.job_profile import (
    GeneratedJobProfile,
    JobProfileBatchDeleteRequest,
    JobProfileBatchDeleteResponse,
    JobProfileGenerateRequest,
)


class JobProfileService:
    """岗位画像服务，负责生成路线分发、结果校验、保存和详情查询。"""

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

    def generate_profile(
        self,
        db: Session,
        request: JobProfileGenerateRequest,
    ) -> JobMarketProfile:
        """
        根据画像类型分发到对应的岗位画像生成路线。
        Args:
            db: 数据库会话。
            request: 岗位画像统一生成请求。
        Returns:
            已保存的岗位画像。
        Raises:
            BusinessException: 对应画像生成路线未开放或生成失败。
        """
        if request.profile_type == "user":
            return self._generate_user_profile(db, request)

        return self._generate_system_profile(db, request)

    def _generate_user_profile(
        self,
        db: Session,
        request: JobProfileGenerateRequest,
    ) -> JobMarketProfile:
        """
        根据用户提交的岗位文本生成并保存用户岗位画像。
        Args:
            db: 数据库会话。
            request: 岗位画像统一生成请求。
        Returns:
            已保存的用户岗位画像。
        """
        self._validate_user_route_request(request)

        if request.use_system_job_data:
            raise BusinessException(code=400, msg="参考系统岗位数据功能暂未开放")

        # user 路线校验完成后，这两个字段必然存在；断言仅用于收窄静态类型。
        assert request.user_id is not None
        assert request.job_text is not None
        cleaned_job_text = self._clean_job_text(request.job_text)

        # 同一次生成只读取一次模板，首次生成和修复阶段复用同一份 Agent 配置。
        template_config = self._load_profile_agent_config(request.agent_id)
        agent_result = self._call_profile_agent(cleaned_job_text, template_config)

        try:
            generated_profile = self._validate_generated_profile(agent_result)
        except (ValueError, ValidationError) as first_error:
            # Agent 可能返回带代码围栏的内容、缺少字段或类型不匹配。
            # 第一版只允许修复一次，避免无限调用模型并产生不可控成本。
            repaired_result = self._repair_agent_output(
                cleaned_job_text=cleaned_job_text,
                agent_result=agent_result,
                validation_error=str(first_error),
                template_config=template_config,
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
            profile_type=request.profile_type,
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

    def _generate_system_profile(
        self,
        db: Session,
        request: JobProfileGenerateRequest,
    ) -> JobMarketProfile:
        """
        处理系统岗位画像生成路线。
        Args:
            db: 数据库会话；系统路线实现后用于读取岗位数据和保存画像。
            request: 岗位画像统一生成请求。
        Returns:
            已保存的系统岗位画像。
        Raises:
            BusinessException: 系统岗位画像生成路线当前尚未开放。
        """
        # 显式保留独立路线入口，后续可在此增加 system 专属参数校验和生成编排。
        raise BusinessException(code=400, msg="系统岗位画像生成功能暂未开放")

    def _validate_user_route_request(self, request: JobProfileGenerateRequest) -> None:
        """
        校验用户岗位画像生成路线需要的参数组合。
        Args:
            request: 岗位画像统一生成请求。
        Raises:
            BusinessException: user 路线缺少用户 ID 或岗位文本。
        """
        missing_fields: list[str] = []
        if not request.user_id:
            missing_fields.append("user_id")
        if not request.job_text:
            missing_fields.append("job_text")

        if missing_fields:
            field_names = "、".join(missing_fields)
            raise BusinessException(
                code=422,
                msg=f"profile_type=user 时以下参数不能为空：{field_names}",
            )

    def list_user_profiles(
        self,
        db: Session,
        *,
        user_id: str,
        page: int = JOB_DEFAULT_PAGE,
        page_size: int = JOB_DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        根据用户 ID 分页查询用户岗位画像。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            page: 当前页码。
            page_size: 每页数量。

        Returns:
            包含岗位画像列表和分页信息的字典。
        """
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), JOB_MAX_PAGE_SIZE)
        rows, total = self.repository.list_user_profiles(
            db,
            user_id=user_id,
            page=safe_page,
            page_size=safe_page_size,
        )
        return {
            "items": rows,
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

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

    def delete_profiles(
        self,
        db: Session,
        request: JobProfileBatchDeleteRequest,
    ) -> JobProfileBatchDeleteResponse:
        """
        批量删除岗位画像。

        对于请求中不存在的画像 ID，会放入 missing_ids 一起返回，不抛异常，
        方便前端一次性提示用户哪些 ID 已经失效。

        Args:
            db: 数据库会话。
            request: 批量删除请求，包含去重后的画像 ID 列表。

        Returns:
            批量删除结果，包含已删除 ID 和缺失 ID。
        """
        existing_profiles = self.repository.list_profiles_by_ids(db, request.profile_ids)
        existing_ids = {profile.id for profile in existing_profiles}
        missing_ids = [
            profile_id for profile_id in request.profile_ids if profile_id not in existing_ids
        ]
        deleted_ids = sorted(existing_ids)

        if existing_profiles:
            self.repository.delete_profiles(db, existing_profiles)

        return JobProfileBatchDeleteResponse(
            requested=len(request.profile_ids),
            deleted=len(deleted_ids),
            deleted_ids=deleted_ids,
            missing_ids=missing_ids,
        )

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

    def _load_profile_agent_config(self, agent_id: str) -> dict[str, Any]:
        """
        从能力层加载调用方指定的岗位画像 Agent 模板配置。

        Args:
            agent_id: 本次岗位画像生成使用的 Agent 模板 ID。

        Returns:
            已通过基础校验的 Agent 模板 config。

        Raises:
            BusinessException: 模板查询失败、模板不存在、被禁用或配置不完整。
        """
        try:
            template = self.capability_agent_client.get_agent_template(agent_id)
        except RuntimeError as error:
            raise BusinessException(code=502, msg=str(error)) from error

        if template is None:
            raise BusinessException(
                code=503,
                msg=f"岗位画像生成 Agent 模板不存在: {agent_id}",
            )
        if template.get("status") != "active":
            raise BusinessException(
                code=503,
                msg=f"岗位画像生成 Agent 模板未启用: {agent_id}",
            )

        config = template.get("config")
        if not isinstance(config, dict):
            raise BusinessException(code=503, msg="岗位画像生成 Agent 模板配置无效")
        if not isinstance(config.get("system_prompt"), str) or not config["system_prompt"].strip():
            raise BusinessException(code=503, msg="岗位画像生成 Agent 模板缺少 system_prompt")
        if not isinstance(config.get("response_format"), dict) or not config["response_format"]:
            raise BusinessException(code=503, msg="岗位画像生成 Agent 模板缺少 response_format")
        return config

    def _call_profile_agent(
        self,
        cleaned_job_text: str,
        template_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        使用岗位画像 Agent 模板调用能力层通用 Agent。

        Args:
            cleaned_job_text: 清理后的岗位文本。
            template_config: 从能力层模板服务读取的 Agent 配置。

        Returns:
            能力层 Agent 运行结果。
        """
        # 固定执行规则由 Agent 模板的 system_prompt 管理；query 只携带本次任务材料。
        query = f"请根据以下岗位材料生成岗位画像：\n\n{cleaned_job_text}"
        payload = self._build_agent_run_payload(query, template_config)
        return self._run_profile_agent(payload)

    def _repair_agent_output(
        self,
        *,
        cleaned_job_text: str,
        agent_result: dict[str, Any],
        validation_error: str,
        template_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        使用同一 Agent 模板请求模型修复一次岗位画像输出。

        Args:
            cleaned_job_text: 原始岗位材料。
            agent_result: 第一次 Agent 运行结果。
            validation_error: 第一次输出的校验错误。
            template_config: 首次生成时加载的 Agent 模板配置。

        Returns:
            修复后的 Agent 运行结果。
        """
        original_output = agent_result.get("structured_output") or agent_result.get("answer") or ""
        query = (
            "请修复下面的岗位画像输出，使其严格符合 response_format 定义的结构。"
            "只能根据原始岗位材料修复，不得补充新事实。\n\n"
            f"原始岗位材料：\n{cleaned_job_text}\n\n"
            f"待修复输出：\n{original_output}\n\n"
            f"校验错误：\n{validation_error}"
        )
        payload = self._build_agent_run_payload(
            query,
            template_config,
            runtime_overrides={"temperature": 0, "max_retries": 1},
        )
        return self._run_profile_agent(payload)

    def _build_agent_run_payload(
        self,
        query: str,
        template_config: dict[str, Any],
        *,
        runtime_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        将 Agent 模板配置展开为 /agent/run 请求参数。

        Args:
            query: 本次岗位画像任务指令。
            template_config: Agent 模板 config。
            runtime_overrides: 本次调用需要覆盖的模型运行参数。

        Returns:
            可直接提交给能力层 /agent/run 的请求体。
        """
        runtime_options = dict(template_config.get("runtime_options") or {})
        if runtime_overrides:
            runtime_options.update(runtime_overrides)

        # query 是每次业务调用产生的动态内容，其余装配参数全部来源于 Agent 模板。
        return {
            "query": query,
            "system_prompt": template_config["system_prompt"],
            "response_format": template_config["response_format"],
            "inputs": {},
            "files": [],
            "tools": list(template_config.get("tools") or []),
            "optional_features": dict(template_config.get("optional_features") or {}),
            "runtime_options": runtime_options,
        }

    def _run_profile_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        执行岗位画像 Agent 请求并转换能力层调用异常。

        Args:
            payload: 已完成模板展开的 /agent/run 请求体。

        Returns:
            能力层 Agent 运行结果。

        Raises:
            BusinessException: 能力层 Agent 调用失败。
        """
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
