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
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DATABASE
MODEL_API_KEY / LLM_API_KEY
MODEL_BASE_URL / LLM_BASE_URL
MODEL_CHAT_MODEL / LLM_MODEL
CHECKPOINTER_TYPE
CHECKPOINTER_POSTGRES_SCHEMA
QCWY_BROWSER_EXECUTABLE_PATH
```
