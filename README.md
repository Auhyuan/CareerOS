# 就业指导 AI 平台后端

这是一个面向就业指导 AI 平台的 Python 后端项目。当前后端已经拆成两个独立 FastAPI 服务：

- `capability-backend`：能力层服务，提供通用 AI 和数据采集能力。
- `orchestration-backend`：编排层服务，提供和就业业务强相关的流程编排与数据入库能力。

Java 后端后续负责登录、权限、用户、组织、页面流程和统一调用入口；Python 后端只负责 AI 能力、爬虫能力、岗位数据处理和业务智能编排。

## 目录结构

```text
get_job_data/
  backend/
    capability-backend/
      app/
        main.py
        server/
          agent/
          spider/
      requirements.txt
      .env.example

    orchestration-backend/
      app/
        main.py
        server/
          job/
      requirements.txt
      .env.example

  docs/
    架构图.md
    AC-验收标准文档.md
    TDD-技术标准文档.md
    ERD-数据库设计.md
    API-SPEC接口文档.md
```

## 服务边界

### capability-backend

能力层只负责通用能力，不直接写业务库。

当前包含：

- Agent 能力：`/agent/*`
- 爬虫能力：`/spider/*`

典型接口：

```text
GET  /agent/health
POST /agent/run
GET  /spider/health
POST /spider/qcwy/jobs
```

注意：`/spider/qcwy/jobs` 只负责采集岗位数据并返回 `rows`，不负责入库。

### orchestration-backend

编排层负责就业平台业务流程和业务数据入库。

当前包含：

- 岗位库查询：`/job/postings/search`
- 岗位方向查询：`/job/directions/search`
- 岗位画像查询：`/job/directions/{direction_id}/profile`
- 前程无忧采集并入库：`/job/crawl/qcwy/jobs`

`/job/crawl/qcwy/jobs` 会调用能力层的 `/spider/qcwy/jobs`，拿到完整岗位数据后再写入 PostgreSQL。

## 调用链路

```text
Java / 前端
  -> orchestration-backend:8091 /job/crawl/qcwy/jobs
      -> capability-backend:8090 /spider/qcwy/jobs
      <- 返回岗位采集 rows
      -> orchestration-backend 写入 PostgreSQL
  <- 返回 crawl_run_id / ingest_stats / rows
```

## 环境要求

建议使用 Conda 创建 Python 环境。

推荐 Python 版本：

```text
Python 3.12
```

安装依赖：

```powershell
conda activate job_spider
cd backend/capability-backend
pip install -r requirements.txt

cd backend/orchestration-backend
pip install -r requirements.txt
```

如果两个服务依赖保持一致，后续可以考虑抽出统一依赖管理方式。

## 配置文件

两个服务各自维护自己的 `.env`。

能力层示例：

```text
backend/capability-backend/.env
```

核心配置：

```env
FASTAPI_HOST="127.0.0.1"
FASTAPI_PORT=8090
QCWY_BROWSER_EXECUTABLE_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"

LLM_PROVIDER="openai_compatible"
LLM_API_KEY="your_llm_api_key"
LLM_BASE_URL="https://api.deepseek.com"
LLM_MODEL="deepseek-chat"
```

编排层示例：

```text
backend/orchestration-backend/.env
```

核心配置：

```env
FASTAPI_HOST="127.0.0.1"
FASTAPI_PORT=8091
CAPABILITY_BASE_URL="http://127.0.0.1:8090"
CAPABILITY_TIMEOUT_SECONDS=180

POSTGRES_HOST="127.0.0.1"
POSTGRES_PORT=5433
POSTGRES_USER="remote_root"
POSTGRES_PASSWORD="your_postgres_password"
POSTGRES_DATABASE="career_ai"
```

## 启动服务

先启动能力层：

```powershell
conda activate job_spider
cd D:\study\get_job_data\backend\capability-backend
python app/main.py
```

默认地址：

```text
http://127.0.0.1:8090
```

再启动编排层：

```powershell
conda activate job_spider
cd D:\study\get_job_data\backend\orchestration-backend
python app/main.py
```

默认地址：

```text
http://127.0.0.1:8091
```

## 常用接口

### 能力层爬虫采集

```http
POST http://127.0.0.1:8090/spider/qcwy/jobs
```

该接口只采集，不入库。

请求示例：

```json
{
  "keywords": ["AI应用开发"],
  "cities": ["深圳"],
  "pages": 1,
  "page_size": 20,
  "fetch_mode": "browser",
  "fields": [],
  "save_raw_json": false,
  "save_csv": false,
  "save_excel": false,
  "browser_headless": false,
  "browser_wait_seconds": 25
}
```

### 编排层采集并入库

```http
POST http://127.0.0.1:8091/job/crawl/qcwy/jobs
```

该接口会调用能力层爬虫，并把结果写入岗位库。

请求示例：

```json
{
  "keywords": ["AI应用开发"],
  "cities": ["深圳"],
  "pages": 1,
  "page_size": 20,
  "fetch_mode": "browser",
  "fields": [],
  "save_raw_json": false,
  "save_csv": false,
  "save_excel": false,
  "persist_to_db": true,
  "browser_headless": false,
  "browser_wait_seconds": 25
}
```

### 查询岗位列表

```http
POST http://127.0.0.1:8091/job/postings/search
```

请求示例：

```json
{
  "keyword": "AI应用开发",
  "city": "深圳",
  "platform": "qcwy",
  "status": "recruiting",
  "page": 1,
  "page_size": 20
}
```

### 运行通用 Agent

```http
POST http://127.0.0.1:8090/agent/run
```

请求示例：

```json
{
  "query": "请总结这些岗位的技能要求",
  "conversation_id": "career-profile-ai-app-dev",
  "system_prompt": "你是就业指导平台的岗位分析专家。",
  "inputs": {},
  "files": [],
  "tools": [],
  "optional_features": {
    "long_term_memory_enabled": false,
    "conversation_context_enabled": true,
    "checkpoint_enabled": true,
    "deferred_tool_filter_enabled": false
  },
  "runtime_options": {
    "model": null,
    "temperature": 0.2,
    "timeout_seconds": 60,
    "max_retries": 2
  }
}
```

## 数据库职责

能力层：

- Agent 会话、Agent 模板、Checkpoint 等通用能力数据可以由能力层维护。
- 爬虫能力不直接写岗位业务表。

编排层：

- 负责岗位业务表入库。
- 负责岗位原始数据和标准岗位数据维护。
- 负责后续岗位画像生成结果写入。

当前核心表：

```text
spider_crawl_runs
job_raw_records
job_postings
job_requirement_analysis
job_directions
job_market_profiles
agent.agent_conversations
agent.agent_messages
agent.agent_templates
```

## 设计文档

根目录 `docs/` 下已经整理了阶段性设计文档：

- `架构图.md`
- `AC-验收标准文档.md`
- `TDD-技术标准文档.md`
- `ERD-数据库设计.md`
- `API-SPEC接口文档.md`

这些文档是当前架构和后续开发的主要依据。

## 后续规划

短期重点：

- 完善岗位采集入库流程。
- 基于岗位数据生成岗位画像。
- 完善当前占位的岗位画像生成编排接口：`/job/profiles/generate`。

中期重点：

- 编排层新增 `job_profile` 模块。
- Agent 工具化读取岗位库数据。
- 使用 LangGraph state 承载中间过程数据。

长期重点：

- 能力层沉淀为通用 Agent / 爬虫 / 模型能力平台。
- 编排层沉淀就业指导业务智能流程。
- Java 层统一承接权限、用户、页面和调用入口。
