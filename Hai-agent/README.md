# Hai-agent

面向会展公司营销策划部门的多阶段活动策划智能体业务后端。

## 当前能力

- 用户注册与登录
- JWT Access Token 鉴权
- 可撤销、可轮换的 Refresh Token
- 按 `user_id` 隔离项目
- 创建项目时自动创建主分支和项目准备根节点
- 通用 JSON 阶段结果保存
- 用户确认后推进到下一节点
- 每个步骤节点独立 `agent_thread_id`
- 根据当前节点自动调用对应的 AI-backend Agent 模板
- 支持 SSE 流式转发、附件和知识库范围透传
- Agent 通过 MCP 自动保存当前阶段结果
- 支持从历史节点创建独立方案分支

## 初始化

1. 安装依赖：

```powershell
pip install -r requirements.txt
```

2. 根据 `.env.example` 创建 `.env`，设置数据库密码和 `JWT_SECRET_KEY`。

3. 在 `career_ai` 数据库执行：

```text
sql/001_initial_schema.sql（表会创建在 `hai_agent` Schema）
```

4. 启动服务：

```powershell
python app/main.py
```

默认接口文档地址：`http://127.0.0.1:8093/docs`。

## 鉴权方式

登录成功后，把 Access Token 放入请求头：

```http
Authorization: Bearer <access_token>
```

项目与工作流接口不接收 `user_id`，后端始终从 Access Token 中解析当前用户。

## 基础测试

```powershell
python -B -m unittest discover -s tests -v
```

该命令不连接数据库，覆盖密码哈希、JWT 类型校验和核心路由注册。

## 固定阶段流程

节点推进顺序由后端注册表控制，前端不能传入下一阶段或 Agent ID：

```text
项目准备 -> 需求确认 -> 策划方向 -> 方案生成 -> 反馈修改
```

各阶段 Agent 模板通过 `.env` 中的以下配置绑定：

```text
PROJECT_PREPARATION_AGENT_ID
REQUIREMENT_CONFIRMATION_AGENT_ID
CREATIVE_DIRECTION_AGENT_ID
PROPOSAL_GENERATION_AGENT_ID
FEEDBACK_REVISION_AGENT_ID
```

`POST /workflow/nodes/advance` 只接收 `node_id` 和 `expected_result_version`。


## 节点 Agent 调用

前端统一调用：

```http
POST /workflow/nodes/messages
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "node_id": "当前节点 UUID",
  "message": "请根据我上传的 Brief 整理项目准备清单",
  "message_type": "text",
  "payload": {},
  "stream": true,
  "file_ids": [],
  "knowledge_base_ids": []
}
```

Hai-agent 会自动完成：

1. 根据 Access Token 校验节点和项目归属。
2. 读取节点绑定的 `agent_id` 和独立 `agent_thread_id`。
3. 组装 `project_context`、`previous_stage_result` 和 `current_stage_result`。
4. 注入 MCP 保存所需的用户、项目、分支、节点、阶段和结果版本。
5. 调用 AI-backend `/agent/messages`，流式模式下原样转发 SSE。
6. 阶段 Agent 确认结果后调用 `save_stage_result`，节点状态变为 `ready`。
7. 用户调用 `/workflow/nodes/advance` 进入下一阶段。

启动完整链路前，必须先将 `agent_configs` 中的五个模板导入 AI-backend，并把 Hai-agent MCP 工具同步为 `hai.save_stage_result`。


## 历史节点创建分支

调用 `POST /workflow/branches/create` 可以从 `ready` 或 `completed` 历史节点派生新分支。新节点复制业务结果作为修改基线，但使用全新的 `agent_thread_id`，不会复用原节点 Checkpoint。详细规则见 [历史节点创建分支](docs/历史节点创建分支.md)。

## MCP 工作流工具

Hai-agent 将 FastMCP 挂载在 http://127.0.0.1:8093/mcp/，当前提供：

- save_stage_result：保存当前节点的通用 JSON 阶段结果。

模型只填写 result 和 summary。项目、分支、节点、阶段、用户与结果版本由 AI-backend
从 Agent Runtime Context 读取业务标识，并通过 X-Agent-* 内部请求头传入。

## 阶段 Agent 模板备份

五个工作流阶段的完整 Agent 模板保存在 [`agent_configs`](agent_configs/README.md) 目录。该目录是数据库模板的数据恢复源，包含稳定 Agent ID、系统提示词、工具和模型运行配置。
