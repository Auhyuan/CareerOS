# capability-backend

`capability-backend` 是就业指导 AI 平台的基础能力层，负责提供可复用的 AI、Agent、工具和爬虫能力。

## 职责边界

能力层只提供通用能力，不直接写岗位业务表。

当前模块：

```text
app/server/agent/      # 通用 Agent 能力
app/server/spider/     # 招聘平台爬虫能力
app/common/            # 通用配置、数据库、响应、异常处理
sql/                   # 能力层数据库脚本
```

## 主要接口

Agent：

```text
GET  /agent/health
GET  /agent/model/config
GET  /agent/capabilities
POST /agent/run
POST /agent/conversations/search
POST /agent/conversations/messages/search
POST /agent/templates/search
POST /agent/templates/upsert
GET  /agent/templates/{agent_id}
```

爬虫：

```text
GET  /spider/health
POST /spider/qcwy/jobs
```

## 数据库

能力层主要使用 `agent` schema：

```text
agent.agent_conversations
agent.agent_messages
agent.agent_templates
agent.checkpoints
agent.checkpoint_blobs
agent.checkpoint_writes
agent.checkpoint_migrations
```

SQL 脚本放在：

```text
backend/capability-backend/sql
```

## 启动

```powershell
cd D:\study\get_job_data\backend\capability-backend
pip install -r requirements.txt
python app/main.py
```

默认地址：

```text
http://127.0.0.1:8090
```

## Agent 运行日志

`/agent/run` 会在控制台记录以下关键阶段：

- 运行时上下文创建和会话历史加载
- Prompt、工具、中间件和 Checkpointer 装配
- 模型网关别名解析与 ChatModel 初始化
- LangChain Agent 创建、执行完成和总耗时
- 执行异常与堆栈

日志不会输出 API Key、完整 Prompt、完整用户问题或结构化输出内容。日志级别通过 `.env` 中的 `LOG_LEVEL` 控制，默认是 `INFO`。

## 模型网关配置

模型连接参数统一配置在 Agent 根目录。首次配置时可参考同目录下的 `model_gateway.example.yaml`，真实文件包含密钥并已被 Git 忽略：

```text
D:\study\get_job_data\backend\capability-backend\app\server\agent\model_gateway.yaml
```

模板中的 `runtime_options.model` 使用模型别名，例如 `chat_main`、`intent_router`。为空时使用 YAML 的 `defaults.chat`。

## 环境变量

配置文件：

```text
.env
.env.example
```

常见配置：

```text
FASTAPI_HOST
FASTAPI_PORT
LOG_LEVEL
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DATABASE
LANGSMITH_TRACING
LANGSMITH_API_KEY
LANGSMITH_ENDPOINT
LANGSMITH_PROJECT
CHECKPOINTER_TYPE
CHECKPOINTER_POSTGRES_SCHEMA
QCWY_BROWSER_EXECUTABLE_PATH
```
