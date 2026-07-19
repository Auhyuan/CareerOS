"""知识入库组件的无外部依赖单元测试。"""

import unittest

from app.server.knowledge.src.ingestion.executor import ingestion_executor
from app.server.knowledge.src.services.knowledge_management_service import knowledge_management_service


class IngestionComponentTestCase(unittest.TestCase):
    """验证入库流程中稳定 ID、上下文和 Collection 命名。"""

    def test_chunk_id_is_stable_and_versioned(self) -> None:
        """相同输入应生成相同 ID，索引版本变化后 ID 必须变化。"""
        first = ingestion_executor._build_chunk_id(
            knowledge_id="kb_test",
            file_id="file_test",
            index_version=1,
            chunk_index=0,
        )
        repeated = ingestion_executor._build_chunk_id(
            knowledge_id="kb_test",
            file_id="file_test",
            index_version=1,
            chunk_index=0,
        )
        rebuilt = ingestion_executor._build_chunk_id(
            knowledge_id="kb_test",
            file_id="file_test",
            index_version=2,
            chunk_index=0,
        )

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, rebuilt)
        self.assertLessEqual(len(first), 100)

    def test_context_uses_header_order(self) -> None:
        """标题元数据应转换为便于引用展示的层级路径。"""
        context = ingestion_executor._build_context(
            {"headers": {"h1": "第一章", "h2": "第二节"}}
        )

        self.assertEqual(context, "第一章 > 第二节")

    def test_collection_name_only_contains_safe_characters(self) -> None:
        """Collection 名称应清理 Milvus 不接受的特殊字符。"""
        name = knowledge_management_service._build_collection_name("kb-test/value")

        self.assertEqual(name, "knowledge_kb_test_value")


if __name__ == "__main__":
    unittest.main()
