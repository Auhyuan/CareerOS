"""Hai-agent 阶段 Agent 配置完整性测试。"""

import json
import unittest
from pathlib import Path


CONFIG_DIR = Path(__file__).resolve().parents[1] / "agent_configs"
EXPECTED_STAGE_CODES = [
    "project_preparation",
    "requirement_confirmation",
    "creative_direction",
    "proposal_generation",
    "feedback_revision",
]


class StageAgentConfigTestCase(unittest.TestCase):
    """验证阶段映射和可恢复模板文件保持一致。"""

    @staticmethod
    def _load_json(path: Path) -> dict:
        """按 UTF-8 读取一个 JSON 配置文件。"""
        return json.loads(path.read_text(encoding="utf-8"))

    def test_manifest_contains_all_fixed_stages(self) -> None:
        """恢复清单必须完整覆盖五个固定工作流阶段。"""
        manifest = self._load_json(CONFIG_DIR / "manifest.json")
        stage_codes = [item["stage_code"] for item in manifest["templates"]]

        self.assertEqual(stage_codes, EXPECTED_STAGE_CODES)
        self.assertEqual(len({item["agent_id"] for item in manifest["templates"]}), 5)

    def test_each_template_is_complete_and_references_save_tool(self) -> None:
        """每个模板都应是可提交给 AI-backend 的完整创建参数。"""
        manifest = self._load_json(CONFIG_DIR / "manifest.json")

        for item in manifest["templates"]:
            with self.subTest(stage_code=item["stage_code"]):
                payload = self._load_json(CONFIG_DIR / item["file"])
                self.assertEqual(payload["agent_id"], item["agent_id"])
                self.assertEqual(payload["status"], "active")
                self.assertTrue(payload["agent_name"])
                self.assertTrue(payload["config"]["system_prompt"])
                self.assertIn("hai.save_stage_result", payload["config"]["tools"])
                self.assertEqual(
                    payload["config"]["runtime_options"]["model_code"],
                    "HK-llm-chatmodel",
                )


    def test_preparation_agent_only_saves_final_confirmed_result(self) -> None:
        """项目准备 Agent 必须先收集资料，不能在每轮交流后自动保存。"""
        payload = self._load_json(CONFIG_DIR / "01_project_preparation_agent.json")
        prompt = payload["config"]["system_prompt"]

        self.assertIn("资料收集过程中", prompt)
        self.assertIn("不得在每轮对话结束时例行调用保存工具", prompt)
        self.assertIn("用户明确确认该清单", prompt)


if __name__ == "__main__":
    unittest.main()
