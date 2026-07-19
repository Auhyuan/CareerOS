"""Agent 知识库能力配置与内部检索工具测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from app.server.agent.src.agent.assembler import AgentAssembler
from app.server.agent.src.runtime.context import AgentRuntimeContext
from app.server.agent.src.schemas.request import (
    AgentOptionalFeatures,
    AgentRunRequest,
    ModelRuntimeOptions,
)
from app.server.agent.src.tools.knowledge_tools import search_knowledge_base
from app.server.knowledge.src.retrieval.schemas import RetrievalOutput, RetrievalResult


class AgentKnowledgeToolTestCase(unittest.IsolatedAsyncioTestCase):
    """验证知识库白名单和检索结果写入 LangGraph state 的行为。"""

    def test_knowledge_base_ids_are_normalized(self) -> None:
        """知识库 ID 应清理空白、去除空值并保持顺序去重。"""
        features = AgentOptionalFeatures(
            knowledge_enabled=True,
            knowledge_base_ids=[" kb_one ", "", "kb_one", "kb_two"],
        )
        self.assertEqual(features.knowledge_base_ids, ["kb_one", "kb_two"])

    def test_enabled_knowledge_requires_base_ids(self) -> None:
        """启用知识库能力但未选择知识库时应立即拒绝配置。"""
        with self.assertRaises(ValidationError):
            AgentOptionalFeatures(knowledge_enabled=True)

    async def test_assembler_injects_knowledge_tool_only_when_enabled(self) -> None:
        """知识库开关开启时，组装器应自动加入内部检索工具。"""
        model_service = MagicMock()
        model_service.create_chat_model.return_value = MagicMock()
        tool_service = MagicMock()
        tool_service.get_tools = AsyncMock(return_value=[])
        prompt_service = MagicMock()
        prompt_service.render_system_prompt.return_value = "system"
        runtime_context_service = MagicMock()
        runtime_context_service.get_context_schema.return_value = AgentRuntimeContext
        middleware_factory = MagicMock()
        middleware_factory.build_langchain_middlewares.return_value = []
        middleware_factory.describe_middlewares.return_value = []
        middleware_factory.describe_state_schemas.return_value = []
        checkpoint_service = MagicMock()

        assembler = AgentAssembler(
            model_service=model_service,
            tool_service=tool_service,
            prompt_service=prompt_service,
            runtime_context_service=runtime_context_service,
            middleware_factory=middleware_factory,
            checkpoint_service=checkpoint_service,
        )
        request = AgentRunRequest(
            query="查询知识",
            optional_features=AgentOptionalFeatures(
                knowledge_enabled=True,
                knowledge_base_ids=["kb_one"],
            ),
            runtime_options=ModelRuntimeOptions(model_code="chat-main"),
        )
        context = AgentRuntimeContext(
            run_id="run-1",
            knowledge_enabled=True,
            knowledge_base_ids=["kb_one"],
        )

        with patch(
            "app.server.agent.src.agent.assembler.create_agent",
            return_value=MagicMock(),
        ) as create_agent_mock:
            await assembler.assemble(request, context)

        tools = create_agent_mock.call_args.kwargs["tools"]
        self.assertEqual(
            [getattr(tool, "name", "") for tool in tools],
            ["search_knowledge_base"],
        )

    async def test_search_writes_current_run_retrieval_context(self) -> None:
        """检索成功后应把证据写入当前 run_id 对应的 retrieval_context。"""
        runtime = SimpleNamespace(
            context={
                "run_id": "run-1",
                "knowledge_enabled": True,
                "knowledge_base_ids": ["kb_one"],
            },
            tool_call_id="tool-call-1",
        )
        output = RetrievalOutput(
            mode="hybrid",
            result_count=1,
            rerank_used=True,
            results=[
                RetrievalResult(
                    collection_name="knowledge_kb_one",
                    chunk_id="chunk-1",
                    file_id="file-1",
                    source="guide.md",
                    chunk_index=0,
                    content="这是检索到的知识证据。",
                    score=0.9,
                )
            ],
        )

        with (
            patch(
                "app.server.agent.src.tools.knowledge_tools._resolve_collection_names",
                return_value=["knowledge_kb_one"],
            ),
            patch(
                "app.server.agent.src.tools.knowledge_tools.knowledge_service.retrieve",
                new=AsyncMock(return_value=output),
            ),
        ):
            command = await search_knowledge_base.coroutine(
                query="如何使用知识库",
                runtime=runtime,
                top_k=3,
            )

        retrieval_items = command.update["retrieval_context"]
        self.assertEqual(retrieval_items[0]["run_id"], "run-1")
        self.assertIn("这是检索到的知识证据", retrieval_items[0]["content"])
        self.assertEqual(command.update["messages"][0].tool_call_id, "tool-call-1")


if __name__ == "__main__":
    unittest.main()
