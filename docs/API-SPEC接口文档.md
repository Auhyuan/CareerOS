# API-SPEC - 接口文档

## 1. 通用约定

### 1.1 基础地址

本地默认：

```text
能力层 capability-backend: http://127.0.0.1:8090
编排层 orchestration-backend: http://127.0.0.1:8091
```

启动方式：

```powershell
cd backend
python app/main.py
```

### 1.2 统一响应

所有业务接口统一返回：

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

### 1.3 权限说明

Python 服务不做登录和权限控制。调用方需要在 Java 层完成权限判断后，再调用 Python 接口。

## 2. Agent 接口

### 2.1 Agent 健康检查

```http
GET /agent/health
```

响应：

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "service": "agent",
    "status": "ok"
  }
}
```

### 2.2 查询模型配置

```http
GET /agent/model/config
```

说明：返回脱敏后的模型配置，只用于环境检查。

响应 data：

```json
{
  "provider": "openai-compatible",
  "base_url": "https://api.example.com/v1",
  "chat_model": "xxx-chat",
  "embedding_model": "xxx-embedding",
  "rerank_model": null,
  "langsmith_tracing": false,
  "langsmith_endpoint": "https://api.smith.langchain.com",
  "langsmith_project": "career-ai",
  "has_api_key": true,
  "has_langsmith_api_key": false
}
```

### 2.3 查询 Agent 能力

```http
GET /agent/capabilities
```

响应 data：

```json
{
  "service_name": "agent",
  "modules": ["agent", "model", "schemas", "prompts", "tools"],
  "enabled_features": ["openai_compatible_chat_model", "postgres_checkpointer"]
}
```

### 2.4 运行通用 Agent

```http
POST /agent/run
```

请求：

```json
{
  "query": "请总结这些岗位的技能要求",
  "conversation_id": "career-profile-ai-app-dev",
  "system_prompt": "你是就业指导平台的岗位分析专家。",
  "inputs": {
    "job_direction": "AI应用开发",
    "job_samples": []
  },
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

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 是 | 本次任务指令。 |
| `conversation_id` | string | 否 | 会话 ID；不传时服务端生成。 |
| `system_prompt` | string | 否 | 本次运行使用的系统提示词。 |
| `inputs` | object | 否 | 编排层注入的业务变量。 |
| `files` | array | 否 | 附件上下文，当前预留。 |
| `tools` | array | 否 | 本次允许使用的工具名。 |
| `optional_features` | object | 否 | 可选能力开关。 |
| `runtime_options` | object | 否 | 模型运行参数。 |

响应 data：

```json
{
  "answer": "模型回复内容",
  "structured_output": {}
}
```

注意：

- `/agent/run` 不接收 `agent_id`。
- `/agent/run` 不接收外部 `input_messages`。
- 历史会话由 `conversation_id` 从 ContextService 获取。
- Checkpoint 用于 LangGraph 状态持久化，不作为跨轮历史来源。

## 3. Agent 会话接口

### 3.1 查询会话

```http
POST /agent/conversations/search
```

请求：

```json
{
  "conversation_id": "career-profile-ai-app-dev"
}
```

响应 data：

```json
{
  "total": 1,
  "items": [
    {
      "conversation_id": "career-profile-ai-app-dev",
      "title": "AI应用开发岗位画像",
      "status": "active",
      "metadata": {},
      "created_at": "2026-06-17T10:00:00+08:00",
      "updated_at": "2026-06-17T10:00:00+08:00"
    }
  ]
}
```

### 3.2 查询会话消息

```http
POST /agent/conversations/messages
```

请求：

```json
{
  "conversation_id": "career-profile-ai-app-dev",
  "limit": 50
}
```

响应 data：

```json
{
  "conversation_id": "career-profile-ai-app-dev",
  "messages": [
    {
      "message_id": "msg_xxx",
      "role": "user",
      "message_type": "user_message",
      "content": "请生成 AI 应用开发岗位画像",
      "structured_content": null,
      "tool_name": null,
      "tool_call_id": null,
      "status": "success",
      "error_message": null,
      "metadata": {}
    }
  ]
}
```

## 4. Agent 模板接口

### 4.1 创建或更新模板

```http
POST /agent/templates/upsert
```

请求：

```json
{
  "agent_id": "job-profile-agent",
  "agent_name": "岗位画像分析 Agent",
  "description": "用于根据招聘数据生成岗位画像",
  "config": {
    "system_prompt": "你是就业指导平台的岗位分析专家。",
    "tools": [],
    "runtime_options": {
      "temperature": 0.2
    }
  },
  "status": "active"
}
```

### 4.2 查询模板详情

```http
POST /agent/templates/detail
```

请求：

```json
{
  "agent_id": "job-profile-agent"
}
```

### 4.3 查询模板列表

```http
POST /agent/templates/search
```

请求：

```json
{
  "keyword": "岗位画像",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

响应 data：

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": []
}
```

## 5. 爬虫接口

### 5.1 爬虫健康检查

```http
GET /spider/health
```

### 5.2 采集前程无忧岗位

```http
POST /spider/qcwy/jobs
```

说明：该接口属于能力层，只负责采集并返回岗位数据，不负责入库。

请求：

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
  "browser_executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "browser_wait_seconds": 25
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `keywords` | string[] | 岗位关键词列表。 |
| `cities` | string[] | 城市名称或城市编码列表。 |
| `pages` | number | 每个关键词和城市组合采集页数。 |
| `page_size` | number | 每页岗位数量。 |
| `fetch_mode` | string | `browser` 或 `requests`。 |
| `fields` | string[] | 返回字段列表；空数组返回全部字段。 |
| `save_raw_json` | boolean | 是否保存原始 JSON 文件。 |
| `save_csv` | boolean | 是否保存 CSV。 |
| `save_excel` | boolean | 是否保存 Excel。 |
| `browser_headless` | boolean | 浏览器是否无头运行。 |
| `browser_executable_path` | string | 本机浏览器路径。 |
| `browser_wait_seconds` | number | 等待岗位接口响应的秒数。 |

响应 data：

```json
{
  "platform": "qcwy",
  "total": 20,
  "rows": [],
  "csv_path": null,
  "excel_path": null
}
```

## 6. 岗位接口

### 6.1 岗位服务健康检查

```http
GET /job/health
```

### 6.2 采集并入库前程无忧岗位

```http
POST /job/crawl/qcwy/jobs
```

说明：该接口属于编排层。它先调用能力层 `/spider/qcwy/jobs` 获取完整岗位数据，再由编排层写入 `spider_crawl_runs`、`job_raw_records`、`job_postings`。

请求：

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
  "browser_executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "browser_wait_seconds": 25
}
```

响应 data：

```json
{
  "platform": "qcwy",
  "total": 20,
  "rows": [],
  "csv_path": null,
  "excel_path": null,
  "crawl_run_id": 1,
  "ingest_stats": {
    "raw_created": 20,
    "posting_created": 18,
    "posting_updated": 2
  }
}
```

### 6.3 查询岗位方向列表

```http
POST /job/directions/search
```

请求：

```json
{
  "keyword": "AI",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

### 6.4 查询岗位方向详情

```http
GET /job/directions/{direction_id}
```

### 6.5 查询岗位方向画像

```http
GET /job/directions/{direction_id}/profile
```

响应 data：

```json
{
  "id": 1,
  "direction_id": 1,
  "job_name": "AI应用开发",
  "job_overview": "岗位概述",
  "responsibilities": [],
  "required_skills": [],
  "preferred_skills": [],
  "education_requirement": "本科及以上",
  "experience_requirement": "1-3年",
  "certificate_requirement": "无强制证书要求",
  "source_job_ids": [],
  "source_filters": {},
  "model_name": "xxx-chat",
  "analysis_version": "v1",
  "created_at": "2026-06-17T10:00:00+08:00",
  "updated_at": "2026-06-17T10:00:00+08:00"
}
```

### 6.6 查询岗位列表

```http
POST /job/postings/search
```

请求：

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

### 6.7 查询岗位详情

```http
GET /job/postings/{job_id}
```

### 6.8 查询岗位原始采集记录

```http
GET /job/postings/{job_id}/raw-records?limit=20
```

## 7. 编排层接口规划

以下接口属于建议新增的编排层，不建议放入 Agent 能力层。

### 7.1 生成岗位画像

```http
POST /job/profiles/generate
```

请求草案：

```json
{
  "direction_id": 1,
  "keyword": "AI应用开发",
  "city": "深圳",
  "sample_limit": 50,
  "agent_template_id": "job-profile-agent",
  "save_profile": true
}
```

响应草案：

```json
{
  "status": "planned",
  "message": "岗位画像生成流程尚未实现，当前接口仅作为 API 分块占位。"
}
```

### 7.2 重新生成岗位画像

```http
POST /job/profiles/regenerate
```

### 7.3 查询岗位画像生成任务

```http
POST /job/profiles/tasks/search
```
