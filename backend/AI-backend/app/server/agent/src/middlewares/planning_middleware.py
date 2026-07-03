"""规划模式中间件：注入任务计划规则，并处理计划确认的 resume_value。"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from typing_extensions import NotRequired

from app.server.agent.src.graph.state import CareerAgentState


class PlanningState(CareerAgentState, total=False):
    """规划模式使用的 LangGraph state 扩展。"""

    # task_plan 存放本次运行生命周期内的任务计划，不直接落业务库。
    task_plan: NotRequired[dict[str, Any]]

    # planning_feedback 存放用户针对 draft 计划提出的修改意见，供下一轮模型调用参考。
    planning_feedback: NotRequired[str | None]

    # resume_value 是 InterruptMiddleware 写入的一次性恢复事件，由业务中间件消费后清理。
    resume_value: NotRequired[dict[str, Any] | None]


class PlanningMiddleware(AgentMiddleware[PlanningState]):
    """处理规划模式的提示词注入和计划确认结果。

    这个中间件只在 optional_features.planning_enabled=true 时装配。
    它不负责触发中断；中断由 InterruptMiddleware 根据 interrupt_enabled 统一处理。
    """

    state_schema = PlanningState

    def __init__(self, enabled: bool = True):
        """初始化规划模式中间件。

        Args:
            enabled: 是否启用规划模式逻辑。
        """
        self.enabled = enabled

    def before_model(self, state: PlanningState, runtime: Any) -> dict[str, Any] | None:
        """在模型调用前消费计划确认的 resume_value。

        Args:
            state: 当前 LangGraph state。
            runtime: LangGraph runtime，本方法当前不直接使用。

        Returns:
            需要合并回 state 的更新；没有可消费事件时返回 None。
        """
        if not self.enabled:
            return None

        resume_value = state.get("resume_value")
        if not isinstance(resume_value, dict):
            return None
        if resume_value.get("type") != "plan_confirmation":
            return None

        data = resume_value.get("data") if isinstance(resume_value.get("data"), dict) else {}
        action = str(data.get("action") or "").strip().lower()
        task_plan = dict(state.get("task_plan") or {})
        if not task_plan:
            # 没有计划可处理时也要清理 resume_value，避免后续模型轮次重复消费。
            return {"resume_value": None}

        if action == "approve":
            task_plan["status"] = "running"
            return {
                "task_plan": task_plan,
                "planning_feedback": None,
                "resume_value": None,
            }

        if action == "revise":
            task_plan["status"] = "draft"
            feedback = str(data.get("feedback") or "").strip()
            return {
                "task_plan": task_plan,
                "planning_feedback": feedback or "用户要求修改任务计划，但没有提供具体修改意见。",
                "resume_value": None,
            }

        if action == "cancel":
            task_plan["status"] = "cancelled"
            return {
                "task_plan": task_plan,
                "planning_feedback": None,
                "resume_value": None,
            }

        # 未识别 action 时保留 draft，并把问题反馈给模型，让模型追问或提示用户重新确认。
        task_plan["status"] = "draft"
        return {
            "task_plan": task_plan,
            "planning_feedback": f"用户确认动作无法识别：{action or 'empty'}。请提示用户重新确认计划。",
            "resume_value": None,
        }

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """在模型调用前注入规划模式规则和当前计划状态。

        Args:
            request: LangChain 模型调用请求。
            handler: 后续模型调用处理器。

        Returns:
            模型调用结果。
        """
        if not self.enabled:
            return await handler(request)

        injected = self._build_planning_prompt(request.state or {})
        current_prompt = getattr(request.system_message, "content", "")
        new_system = SystemMessage(content=f"{current_prompt}\n\n{injected}")
        return await handler(request.override(system_message=new_system))

    def _build_planning_prompt(self, state: dict[str, Any]) -> str:
        """构建追加到 system prompt 末尾的规划模式提示词。

        Args:
            state: 当前 LangGraph state。

        Returns:
            规划模式提示词片段。
        """
        task_plan = state.get("task_plan") if isinstance(state.get("task_plan"), dict) else None
        feedback = state.get("planning_feedback")

        lines = [
            "<planning_mode>",
            "规划模式已启用。",
            "1. 当用户任务需要多步骤执行时，必须先调用 set_task_plan 创建任务计划草稿。",
            "2. set_task_plan 会触发用户确认；用户确认前，不要开始执行计划步骤。",
            "3. 用户确认后，计划状态会变为 running，此时才可以按步骤执行，并用 update_task_step 更新步骤状态。",
            "4. 如果用户要求修改计划，继续调用 set_task_plan 重写 draft 计划。",
            "5. 不能自行修改整体计划状态，整体状态由系统中间件控制。",
        ]

        if task_plan:
            lines.append(f"当前任务计划状态：{task_plan.get('status') or 'unknown'}。")
            lines.append(f"当前任务计划标题：{task_plan.get('title') or ''}。")
        if isinstance(feedback, str) and feedback.strip():
            lines.append(f"用户对计划的修改意见：{feedback.strip()}")
            lines.append("请根据该意见重新调用 set_task_plan，生成新的 draft 计划。")

        lines.append("</planning_mode>")
        return "\n".join(lines)
