# TDD - 技术标准文档

## 1. 目标

本文档定义就业指导 AI 平台 Python 侧的技术标准。这里的 TDD 指 Technical Design Document，用于约束架构、代码组织、接口、数据库、Agent 构建和后续演进方式。

## 2. 服务分层标准

Python 侧建议拆成两类后端：

| 层级 | 建议名称 | 职责 | 示例模块 |
| --- | --- | --- | --- |
| 能力层 | `capability-backend` | 通用 AI 和数据能力，不绑定具体业务流程 | Agent、爬虫、模型、工具、知识库、浏览器自动化 |
| 编排层 | `orchestration-backend` | 业务流程编排，组合能力层完成平台任务 | 岗位画像生成、简历分析、职业规划 |

当前项目可以先保持一个 FastAPI 应用，后续按模块边界迁移。

## 3. 推荐目录标准

单个服务模块建议保持以下结构：

```text
server/<module>/
  api/
    __init__.py
    xxx_api.py
  src/
    schemas/
      request.py
      response.py
    service/
    repository/
    models/
    config/
```

Agent 这类复杂模块可以继续细分：

```text
server/agent/src/
  agent/
  model/
  tools/
  prompts/
  runtime/
  middlewares/
  memory/
  checkpoint/
  graph/
  context/
  templates/
```

## 4. 代码注释标准

根据项目约定：

- 每个函数或方法必须有注释，说明函数作用、核心参数和返回值。
- 核心流程必须写详细注释，例如 Agent 组装、消息清理、工具注入、数据入库。
- 注释要解释业务意图和设计原因，不写无意义重复注释。

## 5. API 标准

### 5.1 统一响应

所有业务接口返回：

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

约定：

- `code=0` 表示成功。
- 业务异常使用明确业务错误码。
- 未知异常由全局异常处理器转换为统一响应。

### 5.2 HTTP 方法

- 查询、搜索、执行类业务接口优先使用 POST，便于统一参数体和后续扩展。
- 健康检查、基础配置查看可以使用 GET。
- 路径命名使用模块前缀，例如 `/agent/run`、`/spider/qcwy/jobs`、`/job/crawl/qcwy/jobs`、`/job/postings/search`。

## 6. 权限边界标准

Python 服务不做用户权限管理：

- 不接收用户权限上下文作为核心业务判断依据。
- 不实现登录、鉴权、菜单权限、数据权限。
- Java 层完成权限校验后调用 Python 接口。
- Python 只做参数校验、业务执行和结果返回。

## 7. Agent 构建标准

### 7.1 `/agent/run` 定位

`/agent/run` 是通用 Agent 执行器，不绑定具体业务和模板。

请求中不应包含：

- `agent_id`
- `request_id`
- `metadata`
- `dry_run`
- 外部 `input_messages`

### 7.2 核心请求参数

```json
{
  "query": "本次任务指令",
  "conversation_id": "可选会话 ID",
  "system_prompt": "可选系统提示词",
  "inputs": {},
  "files": [],
  "tools": [],
  "optional_features": {
    "long_term_memory_enabled": false,
    "conversation_context_enabled": false,
    "checkpoint_enabled": false,
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

### 7.3 组装流程

AgentService 负责组装 Agent：

1. 构建运行上下文。
2. 根据模型配置创建 ChatOpenAI。
3. 根据 `tools` 筛选可用工具。
4. 根据可选能力装配中间件。
5. 根据 `checkpoint_enabled` 装配 PostgreSQL Checkpointer。
6. 使用 LangChain `create_agent` 创建 Agent。
7. 调用时先注入 `RemoveMessage(id=REMOVE_ALL_MESSAGES)` 清理 checkpoint 中的旧消息。
8. 注入 ContextService 读取到的历史消息和当前用户问题。

### 7.4 ContextService 与 Checkpoint 分工

| 能力 | 作用 | 是否跨轮对话作为历史 |
| --- | --- | --- |
| ContextService | 保存用户可见的会话历史，例如用户问题、模型回复、工具消息摘要 | 是 |
| Checkpointer | 保存 LangGraph 单次运行过程状态，例如工具调用、中间变量、图状态 | 否，运行前清理消息避免重复 |

## 8. 工具与中间件标准

工具负责执行动作，中间件负责运行期增强。

示例：

- 知识库工具负责检索。
- 知识库中间件负责保存检索结果到 state，并在下一轮模型调用前注入系统提示词。
- 工具参数中不应暴露给模型的内容通过 runtime context 注入，例如知识库 ID、业务过滤条件。

## 9. 编排层标准

编排层负责把能力组合成业务闭环。

岗位画像生成示例：

1. 接收 Java 层发起的岗位画像生成请求。
2. 查询岗位方向和相关招聘样本。
3. 构造岗位画像分析 prompt。
4. 调用能力层 `/agent/run`。
5. 解析结构化输出。
6. 写入 `job_market_profiles`。
7. 返回任务状态或生成结果。

编排层可以拥有自己的 API、service、repository、schema，不应把流程散落在 Agent 或爬虫模块里。

招聘数据采集入库示例：

1. 编排层接收 `/job/crawl/qcwy/jobs` 请求。
2. 编排层创建 `spider_crawl_runs` 运行记录。
3. 编排层调用能力层 `/spider/qcwy/jobs` 获取完整岗位 rows。
4. 编排层写入 `job_raw_records` 和 `job_postings`。
5. 编排层更新采集任务状态并返回入库统计。

能力层爬虫接口不得直接依赖岗位库模型，也不得直接调用 JobService。

## 10. 数据库标准

- PostgreSQL 是当前唯一持久化组件，暂不引入 Redis。
- Agent 相关表放入 `agent` schema。
- 岗位和爬虫相关表当前放入 `public` schema，后续可按需要拆成 `job`、`spider` schema。
- 原始招聘数据必须保留到 `job_raw_records`，方便后续重新分析。
- 标准化岗位数据写入 `job_postings`。
- 聚合画像写入 `job_market_profiles`。
- JSONB 用于保存不稳定结构，例如原始 JSON、模型输出、模板配置。

## 11. 可观测性标准

- 本地服务启动时做 PostgreSQL 健康检查。
- 关键业务流程需要记录日志。
- Agent 调用链路优先接入 LangSmith，用于定位模型调用、工具调用和图状态问题。
- Python 层不强制保留 `request_id`，调用链追踪优先依赖 LangSmith 和服务日志。

## 12. 迁移路径

短期：

- 保持当前 `backend/app/main.py` 单应用。
- 在文档和代码边界上区分能力层与编排层。
- 新增岗位画像生成时，优先放入独立编排模块。

中期：

- 抽出 `capability_app`，保留 Agent、Spider、Model、Tools。
- 抽出 `orchestration_app`，放岗位画像、简历分析、职业规划。
- 两个应用共用数据库和部分 common 工具。

长期：

- 能力层成为通用 Agent/AI 能力平台。
- 编排层成为就业指导业务智能中台。
- Java 层作为统一业务入口和权限控制层。
