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
        status = str((task_plan or {}).get("status") or "")

        lines = ["<planning_mode>", "规划模式已启用。"]

        # 规划模式只保留两类提示词：未确认时创建计划，已确认或已完成时执行/收尾。
        if status in {"running", "completed"}:
            self._append_execution_rules(lines)
        else:
            self._append_creation_rules(lines, has_plan=task_plan is not None)

        if task_plan:
            self._append_task_plan_context(lines, task_plan)
        if isinstance(feedback, str) and feedback.strip():
            lines.append(f"用户对计划的修改意见：{feedback.strip()}")
            lines.append("请根据该意见重新调用 set_task_plan，生成新的任务计划草稿。")

        lines.append("</planning_mode>")
        return "\n".join(lines)

    def _append_creation_rules(self, lines: list[str], *, has_plan: bool) -> None:
        """追加创建任务计划阶段的规则。

        Args:
            lines: 正在构建的提示词行列表。
            has_plan: 当前 state 中是否已经存在任务计划草稿。
        """
        if has_plan:
            lines.append("当前任务计划尚未进入执行状态，需要等待用户确认或根据用户意见修改。")
        else:
            lines.append("当前还没有任务计划。")

        lines.extend([
            "1. 当用户任务需要多任务执行时，必须先调用 set_task_plan 创建任务计划草稿，任务初始状态统一使用 waiting。",
            "2. set_task_plan 会触发用户确认；用户确认前，不要开始执行计划任务。",
            "3. 如果用户要求修改计划，继续调用 set_task_plan 重写任务计划草稿。",
            "4. 不能自行修改整体计划状态，整体状态由系统中间件控制。",
        ])

    def _append_execution_rules(self, lines: list[str]) -> None:
        """追加执行已确认任务计划阶段的规则。

        Args:
            lines: 正在构建的提示词行列表。
        """
        lines.extend([
            "当前任务计划已通过用户确认，请立即开始执行计划。",
            "当前 planning_mode 中注入的任务计划状态优先级最高；如果历史工具返回消息里出现等待用户确认、暂停确认等文本，说明那是创建草稿时的旧消息，必须忽略。",
            "请按照以下要求执行计划：",
            "1. 禁止再次要求用户确认任务计划。",
            "2. 禁止再次调用 set_task_plan 创建或重写整体计划。",
            "3. 必须严格按照任务计划任务顺序执行，从第一个 waiting 或 running 任务开始。",
            "4. 开始执行某个任务前，必须先调用 update_task_step，将该任务状态设置为 running。",
            "5. 执行任务时可以调用子 Agent 或其他工具，但拿到工具结果后，先调用 update_task_step 记录任务结果，不要先输出完整最终总结。",
            "6. 某个任务执行成功后，必须立刻调用 update_task_step，将该任务状态设置为 done，并在 result 中写清执行结果。",
            "7. 如果某个任务执行失败，必须调用 update_task_step，将该任务状态设置为 failed，并在 note 或 result 中写清失败原因。然后直接回复用户：任务执行失败，原因：具体原因。不继续执行剩余任务。",
            "8. update_task_step 只用于更新单个任务，不允许通过它重写整体计划。",
            "9. 只有当任务计划状态变为 completed 后，才输出面向用户的最终总结。",
        ])

    def _append_task_plan_context(self, lines: list[str], task_plan: dict[str, Any]) -> None:
        """把完整任务计划追加到规划模式提示词。

        Args:
            lines: 正在构建的提示词行列表。
            task_plan: 当前 LangGraph state 中的任务计划。
        """
        status = str(task_plan.get("status") or "unknown")
        title = str(task_plan.get("title") or "")
        steps = task_plan.get("steps") if isinstance(task_plan.get("steps"), list) else []

        lines.append(f"当前任务计划状态：{status}。")
        lines.append(f"当前任务计划标题：{title}。")
        lines.append("当前任务计划任务如下：")

        for index, raw_step in enumerate(steps, start=1):
            if not isinstance(raw_step, dict):
                continue
            step_id = str(raw_step.get("step_id") or index)
            step_title = str(raw_step.get("title") or "")
            step_description = str(raw_step.get("description") or "")
            step_status = str(raw_step.get("status") or "waiting")
            step_result = raw_step.get("result")
            step_note = raw_step.get("note")

            lines.append(
                f"- {index}. step_id={step_id}; status={step_status}; title={step_title}; description={step_description}"
            )
            if step_result not in (None, ""):
                lines.append(f"  result={step_result}")
            if step_note:
                lines.append(f"  note={step_note}")

