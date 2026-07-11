import logging
import re
from typing import Any

from sqlmodel import Session

from app.common.core.exceptions import BusinessException
from app.server.job.src.config.job_config import JOB_DEFAULT_PAGE, JOB_DEFAULT_PAGE_SIZE, JOB_MAX_PAGE_SIZE
from app.server.job.src.clients import AIBackendAgentClient
from app.server.job.src.models.job_model import JobMarketProfile
from app.server.job.src.repository.job_repository import JobRepository
from app.server.job.src.repository.job_skill_repository import JobSkillRepository
from app.server.job.src.schemas.job_profile import (
    GeneratedJobProfile,
    JobProfileBatchDeleteRequest,
    JobProfileBatchDeleteResponse,
    JobProfileGenerateRequest,
    JobProfileSaveRequest,
)
from app.server.job.src.schemas.response import JobProfileGenerateResponse


logger = logging.getLogger("orchestration.job.profile")


class JobProfileService:
    """岗位画像服务，负责生成路线分发、结果校验、保存和详情查询。"""

    def __init__(
        self,
        repository: JobRepository | None = None,
        skill_repository: JobSkillRepository | None = None,
        ai_backend_agent_client: AIBackendAgentClient | None = None,
    ):
        """
        初始化岗位画像服务。
        Args:
            repository: 岗位库数据访问对象。
            skill_repository: 岗位技能数据访问对象，用于校验并回填标准技能名称。
            ai_backend_agent_client: 能力层通用 Agent 客户端。
        """
        self.repository = repository or JobRepository()
        self.skill_repository = skill_repository or JobSkillRepository()
        self.ai_backend_agent_client = ai_backend_agent_client or AIBackendAgentClient()

    def generate_profile(self, request: JobProfileGenerateRequest) -> JobProfileGenerateResponse:
        """根据画像类型分发到对应的岗位画像生成路线。

        Args:
            request: 岗位画像统一生成请求。

        Returns:
            Agent 运行 ID 和最终回复。

        Raises:
            BusinessException: 对应画像生成路线未开放或 Agent 执行失败。
        """
        if request.profile_type == "user":
            return self._generate_user_profile(request)
        return self._generate_system_profile(request)

    def _generate_user_profile(
        self,
        request: JobProfileGenerateRequest,
    ) -> JobProfileGenerateResponse:
        """调用岗位画像 Agent，由 Agent 通过工具保存用户岗位画像。

        profile_type 和 user_id 会作为可信运行上下文传给 Agent，并由工具参数
        注入中间件写入 save_job_profile。生成接口只返回 Agent 最终回复。

        Args:
            request: 岗位画像统一生成请求。

        Returns:
            Agent 运行 ID 和最终回复。
        """
        self._validate_user_route_request(request)
        if request.use_system_job_data:
            raise BusinessException(code=400, msg="参考系统岗位数据功能暂未开放")

        # user 路线校验完成后，这两个字段必然存在；断言仅用于收窄静态类型。
        assert request.user_id is not None
        assert request.job_text is not None
        cleaned_job_text = self._clean_job_text(request.job_text)
        logger.info(
            "Job profile generation started: user_id=%s agent_id=%s text_length=%d",
            request.user_id,
            request.agent_id,
            len(cleaned_job_text),
        )

        # 模板决定提示词、模型和工具；请求只提供岗位材料与可信业务参数。
        template_config = self._load_profile_agent_config(request.agent_id)
        agent_result = self._call_profile_agent(
            cleaned_job_text,
            template_config,
            profile_type=request.profile_type,
            user_id=request.user_id,
        )
        run_id = agent_result.get("run_id")
        answer = agent_result.get("answer")
        if not isinstance(run_id, str) or not run_id.strip():
            raise BusinessException(code=502, msg="岗位画像 Agent 未返回运行 ID")
        if not isinstance(answer, str) or not answer.strip():
            raise BusinessException(code=502, msg="岗位画像 Agent 未返回最终回复")

        # 自然语言可能误报成功，必须以真实 save_job_profile ToolMessage 为准。
        save_result = self._extract_save_profile_result(agent_result)
        profile_id = save_result.get("profile_id")
        if save_result.get("saved") is not True or not isinstance(profile_id, int):
            raise BusinessException(code=502, msg="岗位画像 Agent 未成功保存岗位画像")

        logger.info(
            "Job profile agent finished: run_id=%s profile_id=%s user_id=%s",
            run_id,
            profile_id,
            request.user_id,
        )
        return JobProfileGenerateResponse(run_id=run_id, answer=answer)

    def _extract_save_profile_result(self, agent_result: dict[str, Any]) -> dict[str, Any]:
        """从 Agent 实际工具结果中提取岗位画像保存结果。

        Args:
            agent_result: AI-backend 返回的 Agent 运行结果。

        Returns:
            save_job_profile 的结构化执行结果。

        Raises:
            BusinessException: Agent 没有执行保存工具或工具结果格式异常。
        """
        tool_results = agent_result.get("tool_results")
        if not isinstance(tool_results, list):
            raise BusinessException(code=502, msg="岗位画像 Agent 未返回工具执行记录")

        save_results = [
            item.get("content")
            for item in tool_results
            if isinstance(item, dict) and item.get("tool_name") == "save_job_profile"
        ]
        if not save_results:
            raise BusinessException(code=502, msg="岗位画像 Agent 未调用 save_job_profile")

        # 若模型因参数修复多次调用保存工具，以最后一次真实执行结果作为最终状态。
        final_result = save_results[-1]
        if not isinstance(final_result, dict):
            raise BusinessException(code=502, msg="save_job_profile 返回格式异常")
        return final_result

    def save_profile(self, db: Session, request: JobProfileSaveRequest) -> JobMarketProfile:
        """校验 Agent 提交的岗位画像并保存到数据库。

        Args:
            db: 数据库会话。
            request: 画像类型、用户归属和完整岗位画像内容。

        Returns:
            已写入数据库的岗位画像。

        Raises:
            BusinessException: 技能 ID 不存在或画像业务规则不满足。
        """
        generated_profile = request.profile.model_copy(deep=True)
        self._canonicalize_profile_skills(db, generated_profile)
        try:
            self._validate_profile_business_rules(generated_profile)
        except ValueError as error:
            raise BusinessException(code=422, msg=str(error)) from error

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
        saved_profile = self.repository.create_profile(profile, db)
        logger.info(
            "Agent tool persisted job profile: profile_id=%s profile_type=%s user_id=%s job_name=%s",
            saved_profile.id,
            saved_profile.profile_type,
            saved_profile.user_id,
            saved_profile.job_name,
        )
        return saved_profile

    def _canonicalize_profile_skills(self, db: Session, profile: GeneratedJobProfile) -> None:
        """校验技能 ID，并使用技能库中的标准名称覆盖模型生成名称。

        Args:
            db: 数据库会话。
            profile: 待保存的岗位画像，方法会原地回填标准技能名称。

        Raises:
            BusinessException: 任一技能 ID 在 job_skills 表中不存在。
        """
        all_skills = [*profile.required_skills, *profile.preferred_skills]
        skill_ids = list(dict.fromkeys(item.skill_id for item in all_skills))
        persisted_skills = self.skill_repository.list_by_ids(db, skill_ids)
        skill_name_by_id = {skill.id: skill.name for skill in persisted_skills if skill.id is not None}
        missing_ids = [skill_id for skill_id in skill_ids if skill_id not in skill_name_by_id]
        if missing_ids:
            raise BusinessException(
                code=422,
                msg="岗位画像包含不存在的技能 ID: " + ", ".join(map(str, missing_ids)),
            )

        # 名称以平台技能库为准，避免模型传入同一 skill_id 却使用不同名称。
        for item in all_skills:
            item.name = skill_name_by_id[item.skill_id]

    def _generate_system_profile(
        self,
        request: JobProfileGenerateRequest,
    ) -> JobProfileGenerateResponse:
        """
        处理系统岗位画像生成路线。
        Args:
            request: 岗位画像统一生成请求。
        Returns:
            Agent 运行 ID 和最终回复。
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
            template = self.ai_backend_agent_client.get_agent_template(agent_id)
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
        return config

    def _call_profile_agent(
        self,
        cleaned_job_text: str,
        template_config: dict[str, Any],
        *,
        profile_type: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        """使用岗位画像 Agent 模板调用能力层通用 Agent。

        Args:
            cleaned_job_text: 清理后的岗位文本。
            template_config: 从能力层模板服务读取的 Agent 配置。
            profile_type: 由业务接口校验后的画像类型。
            user_id: 由业务接口校验后的用户 ID。

        Returns:
            能力层 Agent 运行结果。
        """
        # 固定规则由模板 system_prompt 管理；消息只携带本次岗位材料。
        query = f"请根据以下岗位材料生成并保存岗位画像：\n\n{cleaned_job_text}"
        payload = self._build_agent_run_payload(
            query,
            template_config,
            trusted_inputs={"profile_type": profile_type, "user_id": user_id},
        )
        return self._run_profile_agent(payload)

    def _build_agent_run_payload(
        self,
        query: str,
        template_config: dict[str, Any],
        *,
        trusted_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """将 Agent 模板配置展开为 /agent/messages 请求参数。

        Args:
            query: 本次岗位画像任务指令。
            template_config: Agent 模板 config。
            trusted_inputs: 由编排层校验后传给工具注入中间件的业务参数。

        Returns:
            可直接提交给能力层 /agent/messages 的请求体。
        """
        # profile_type/user_id 不作为模型可填写的工具参数，而由 Runtime Context 注入。
        return {
            "message": query,
            "message_type": "text",
            # 服务间调用需要一次性 JSON 响应；SSE 仅供前端实时展示使用。
            "stream": False,
            "payload": {},
            "system_prompt": template_config["system_prompt"],
            "inputs": trusted_inputs,
            "files": [],
            "tools": list(template_config.get("tools") or []),
            "optional_features": dict(template_config.get("optional_features") or {}),
            "runtime_options": dict(template_config.get("runtime_options") or {}),
        }

    def _run_profile_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        执行岗位画像 Agent 请求并转换能力层调用异常。

        Args:
            payload: 已完成模板展开的 /agent/messages 请求体。

        Returns:
            能力层 Agent 运行结果。

        Raises:
            BusinessException: 能力层 Agent 调用失败。
        """
        try:
            return self.ai_backend_agent_client.run_agent(payload)
        except RuntimeError as error:
            raise BusinessException(code=502, msg=str(error)) from error

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
