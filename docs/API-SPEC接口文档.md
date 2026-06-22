# API-SPEC - 接口文档

## 1. 通用约定

本地默认地址：

```text
capability-backend:    http://127.0.0.1:8090
orchestration-backend: http://127.0.0.1:8091
```

统一响应结构：

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

Python 服务不做登录和权限控制。调用方需要在 Java 层完成权限判断后，再调用 Python 接口。

## 2. 能力层 Agent 接口

### 2.1 健康检查

```http
GET /agent/health
```

### 2.2 查询模型配置

```http
GET /agent/model/config
```

说明：返回脱敏后的模型配置，用于环境检查。

### 2.3 查询 Agent 能力

```http
GET /agent/capabilities
```

### 2.4 运行 Agent

```http
POST /agent/run
```

请求示例：

```json
{
  "query": "请总结这些岗位的技能要求",
  "conversation_id": "career-profile-ai-app-dev",
  "system_prompt": "你是就业指导平台的岗位分析专家。",
  "response_format": null,
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
    "model": "chat_main",
    "temperature": 0.2,
    "timeout_seconds": null,
    "max_retries": 2
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 是 | 当前用户问题或任务指令。 |
| `conversation_id` | string | 否 | 会话 ID；不传时服务端生成。 |
| `system_prompt` | string | 否 | 本次运行使用的系统提示词。 |
| `response_format` | object | 否 | 结构化输出 JSON Schema；不传、传 `null` 或 `{}` 时不启用。 |
| `inputs` | object | 否 | 编排层注入的业务变量。 |
| `files` | array | 否 | 文件输入，当前预留。 |
| `tools` | array | 否 | 本次允许使用的工具名。 |
| `optional_features` | object | 否 | 可选能力开关。 |
| `runtime_options` | object | 否 | 模型运行参数。 |

`runtime_options.model` 使用 Agent 根目录 `model_gateway.yaml` 中的模型别名；为空时使用 `defaults.chat`。`timeout_seconds` 为空时使用对应模型的 `timeout`。

注意：

- `/agent/run` 不接收 `agent_id`。
- `/agent/run` 不接收外部 `input_messages`。
- 历史会话通过 `conversation_id` 从 ContextService 获取。
- Checkpoint 用于 LangGraph 状态持久化，不作为跨轮历史来源。
- `response_format` 非空时，结构化结果通过 `data.structured_output` 返回。

## 3. Agent 会话接口

### 3.1 查询会话列表

```http
POST /agent/conversations/search
```

请求示例：

```json
{
  "conversation_id": "career-profile-ai-app-dev",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

### 3.2 查询会话消息

```http
POST /agent/conversations/messages/search
```

请求示例：

```json
{
  "conversation_id": "career-profile-ai-app-dev",
  "page": 1,
  "page_size": 50
}
```

## 4. Agent 模板接口

### 4.1 创建或更新模板

```http
POST /agent/templates/upsert
```

请求示例：

```json
{
  "agent_id": "job-profile-agent",
  "agent_name": "岗位画像分析 Agent",
  "description": "用于根据招聘数据生成岗位画像",
  "config": {
    "system_prompt": "你是就业指导平台的岗位分析专家。",
    "response_format": {
      "type": "object",
      "properties": {
        "job_name": {"type": "string"}
      },
      "required": ["job_name"],
      "additionalProperties": false
    },
    "tools": [],
    "optional_features": {
      "conversation_context_enabled": true,
      "checkpoint_enabled": true
    },
    "runtime_options": {
      "model": null,
      "temperature": 0.1,
      "timeout_seconds": 60,
      "max_retries": 2
    }
  },
  "status": "active"
}
```

### 4.2 查询模板详情

```http
POST /agent/templates/detail
```

请求示例：

```json
{
  "agent_id": "job-profile-agent"
}
```

### 4.3 查询模板列表

```http
POST /agent/templates/search
```

## 5. 爬虫能力接口

### 5.1 爬虫健康检查

```http
GET /spider/health
```

### 5.2 采集前程无忧岗位

```http
POST /spider/qcwy/jobs
```

说明：该接口属于能力层，只负责采集并返回岗位数据，不负责入库。

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
  "browser_executable_path": "",
  "browser_wait_seconds": 25
}
```

## 6. 岗位业务接口

### 6.1 岗位服务健康检查

```http
GET /job/health
```

### 6.2 采集并入库前程无忧岗位

```http
POST /job/crawl/qcwy/jobs
```

说明：该接口属于编排层。它先调用能力层 `/spider/qcwy/jobs` 获取完整岗位数据，再写入 `spider_crawl_runs` 和 `job_raw_records`。

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
  "browser_executable_path": "",
  "browser_wait_seconds": 25
}
```

响应示例：

```json
{
  "platform": "qcwy",
  "total": 20,
  "rows": [],
  "csv_path": null,
  "excel_path": null,
  "crawl_run_id": 1,
  "ingest_stats": {
    "raw_created": 20
  }
}
```

### 6.3 查询原始岗位列表

```http
POST /job/raw-records/search
```

请求示例：

```json
{
  "keyword": "AI应用开发",
  "city": "深圳",
  "platform": "qcwy",
  "page": 1,
  "page_size": 20
}
```

### 6.4 查询原始岗位详情

```http
GET /job/raw-records/{raw_record_id}
```

### 6.5 查询岗位方向列表

```http
POST /job/directions/search
```

请求示例：

```json
{
  "keyword": "AI",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

### 6.6 查询岗位方向详情

```http
GET /job/directions/{direction_id}
```

### 6.7 查询岗位画像详情

```http
GET /job/profiles/{profile_id}
```

### 6.8 生成岗位画像

```http
POST /job/profiles/generate
```

该接口是岗位画像统一生成入口，根据 `profile_type` 进入不同生成路线。

请求示例：

```json
{
  "profile_type": "user",
  "agent_id": "job-profile-agent",
  "user_id": "10001",
  "job_text": "用户粘贴的岗位名称、岗位职责和任职要求等文本",
  "use_system_job_data": false
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `profile_type` | string | 是 | 画像类型：`user` 或 `system`。 |
| `agent_id` | string | 是 | 本次生成使用的 Agent 模板 ID。 |
| `user_id` | string | 条件必填 | `profile_type=user` 时必填。 |
| `job_text` | string | 条件必填 | `profile_type=user` 时必填，最大 50000 字符。 |
| `use_system_job_data` | boolean | 否 | user 路线是否参考系统岗位数据；默认 `false`，当前暂未开放。 |

当前路线：

```text
profile_type = user
执行用户岗位画像生成流程。

profile_type = system
预留系统岗位画像生成流程，当前明确返回功能暂未开放。
```

用户画像处理流程：

1. 根据 `agent_id` 查询启用中的 Agent 模板。
2. 校验并清理 `job_text`。
3. 展开模板的系统提示词、结构化输出、工具和运行参数。
4. 调用能力层 `/agent/run`。
5. 从 `structured_output` 或 `answer` 中提取岗位画像 JSON。
6. 使用 Pydantic 校验结构和技能规则。
7. 首次校验失败时复用同一模板请求 Agent 修复一次。
8. 编排层使用请求中的 `user_id` 和 `profile_type=user`。
9. 写入 `job_market_profiles` 并返回保存后的画像。

注意：

- Agent 只能依据用户提供的 `job_text` 生成画像。
- 除 `job_name` 外，缺失文本返回 `null`，缺失列表返回 `[]`。
- `use_system_job_data=true` 时当前返回“参考系统岗位数据功能暂未开放”。
- `profile_type=user` 但缺少 `user_id` 或 `job_text` 时返回参数校验错误。
- `profile_type=system` 时当前返回“系统岗位画像生成功能暂未开放”。
