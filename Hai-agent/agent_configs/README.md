# Hai-agent 阶段 Agent 配置

该目录是五个阶段 Agent 模板的版本库恢复源。AI-backend 数据库中的模板用于运行，目录中的 JSON 用于版本管理、审查和数据丢失后的重新导入。

## 文件说明

| 顺序 | 阶段 | Agent ID | 配置文件 |
|---|---|---|---|
| 1 | 项目准备 | `hai-project-preparation-agent` | `01_project_preparation_agent.json` |
| 2 | 需求确认 | `hai-requirement-confirmation-agent` | `02_requirement_confirmation_agent.json` |
| 3 | 策划方向 | `hai-creative-direction-agent` | `03_creative_direction_agent.json` |
| 4 | 方案生成 | `hai-proposal-generation-agent` | `04_proposal_generation_agent.json` |
| 5 | 反馈修改 | `hai-feedback-revision-agent` | `05_feedback_revision_agent.json` |

`manifest.json` 保存阶段、Agent ID 和文件之间的稳定映射，后续可以直接作为自动同步脚本的数据源。

## 导入方式

每个阶段 JSON 都是 `POST http://127.0.0.1:8090/agent/templates/upsert` 的完整请求体，可以直接调用接口创建或覆盖同名模板。导入前需要确保：

1. AI-backend 已存在 `HK-llm-chatmodel` 聊天模型配置；如模型编码不同，统一修改五个文件中的 `runtime_options.model_code`。
2. Hai-agent MCP 服务已经在 AI-backend 同步，并且 `save_stage_result` 的平台工具编码为 `hai.save_stage_result`；如果同步时使用了其他前缀，需要同步修改五个文件中的 `tools`。
3. Hai-agent 的 `.env` 中五个阶段 Agent ID 与 `manifest.json` 保持一致。

## 动态提示词变量

模板只保存稳定角色和阶段规则，以下内容由 Hai-agent 每次调用时通过 `inputs` 动态注入：

- `project_context`：项目基础信息。
- `previous_stage_result`：上一节点的最终结果。
- `current_stage_result`：当前节点已经保存的结果，适合继续修改。
- `user_id`、`project_id`、`branch_id`、`node_id`、`stage_code`、`expected_result_version`：供 MCP Runtime Context 自动注入，模型无需填写。

模板中的 `{{project_context}}`、`{{previous_stage_result}}` 和 `{{current_stage_result}}` 会由 AI-backend 的 PromptService 在 Agent 组装阶段替换。

## 维护规则

1. 在平台修改阶段模板后，同步更新对应 JSON，避免数据库和版本库长期漂移。
2. `agent_id` 是稳定业务标识，不要随意修改；展示名称和提示词可以迭代。
3. 不要把项目数据、用户数据、知识库 ID 或密钥写入模板文件。
4. 新增阶段时，同时更新配置文件、`manifest.json`、Hai-agent 阶段注册表和环境变量示例。
