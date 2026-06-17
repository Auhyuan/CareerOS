# TDD - 技术标准文档

本文档定义就业指导 AI 平台 Python 侧的技术标准。这里的 TDD 指 Technical Design Document，用于约束架构、代码组织、接口、数据库、Agent 构建和后续演进方式。

## 1. 分层架构

| 层级 | 服务 | 职责 | 示例 |
| --- | --- | --- | --- |
| 能力层 | `capability-backend` | 提供通用 AI 和数据能力，不绑定具体业务流程 | Agent、模型调用、工具注册、爬虫采集 |
| 编排层 | `orchestration-backend` | 组合能力层完成就业平台业务流程 | 岗位画像生成、岗位数据入库、简历分析 |
| Java 层 | Java 后端 | 登录、权限、用户、菜单、页面流程和统一调用入口 | 用户管理、权限校验、前端接口聚合 |

## 2. 服务模块结构

每个服务模块建议保持以下结构：

```text
server/{module}/
  api/                  # 对外接口层
  src/
    clients/            # 外部服务客户端
    config/             # 模块配置
    models/             # 数据库模型
    repository/         # 数据访问层
    schemas/            # 请求/响应模型
    service/            # 业务服务层
```

Agent 这类复杂模块可以继续细分：

```text
agent/src/
  agent/                # Agent 组装入口
  checkpoint/           # LangGraph checkpoint
  context/              # 会话历史
  graph/                # LangGraph state / graph 预留
  memory/               # 长期记忆预留
  middlewares/          # 中间件
  model/                # ChatOpenAI / Embedding 配置
  prompts/              # prompt 渲染
  runtime/              # runtime context
  templates/            # Agent 模板
  tools/                # 工具注册和筛选
```

## 3. 注释标准

根据项目约定：

- 每个函数或方法必须有注释，说明函数作用、核心参数和返回值。
- 核心流程必须写详细注释，例如 Agent 组装、消息清理、工具注入、数据入库。
- 注释要解释业务意图和设计原因，避免只重复代码本身。

## 4. 统一响应

所有业务接口统一返回：

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

## 5. 接口方法约定

- 查询、搜索、执行业务流程类接口优先使用 POST，方便统一参数体和后续扩展。
- 健康检查、基础配置查看可以使用 GET。
- 路径命名使用模块前缀，例如 `/agent/run`、`/spider/qcwy/jobs`、`/job/crawl/qcwy/jobs`、`/job/raw-records/search`。

## 6. Agent 运行标准

`/agent/run` 是通用 Agent 执行入口，不绑定具体业务。

AgentService 负责组装 Agent：

1. 构建运行上下文。
2. 根据模型配置创建 ChatOpenAI。
3. 根据 `tools` 筛选可用工具。
4. 根据可选能力装配中间件。
5. 根据 `checkpoint_enabled` 装配 PostgreSQL Checkpointer。
6. 使用 LangChain `create_agent` 创建 Agent。
7. 运行时先清理 checkpoint 中的旧 messages，避免与 ContextService 历史重复。
8. 注入 ContextService 读取到的历史消息和当前用户问题。

## 7. ContextService 与 Checkpointer

| 组件 | 作用 | 是否作为跨轮历史来源 |
| --- | --- | --- |
| ContextService | 保存用户可见的会话历史，例如用户问题、模型回复、工具消息摘要 | 是 |
| Checkpointer | 保存 LangGraph 单次运行过程状态，例如工具调用、中间变量、图状态 | 否 |

关键原则：

- 跨轮对话历史只从 ContextService 读取。
- Checkpointer 用于状态持久化、恢复和排查。
- 运行开始时清理 checkpoint 中旧 messages，避免双历史。

## 8. 工具与中间件标准

工具负责执行动作，中间件负责运行期增强。

示例：

- 知识库工具负责检索。
- 知识库中间件负责保存检索结果到 state，并在下一轮模型调用前注入系统提示词。
- 不应暴露给模型的业务参数通过 runtime context 注入，例如知识库 ID、业务过滤条件。

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

招聘数据采集入库示例：

1. 编排层接收 `/job/crawl/qcwy/jobs` 请求。
2. 编排层创建 `spider_crawl_runs` 运行记录。
3. 编排层调用能力层 `/spider/qcwy/jobs` 获取完整岗位 rows。
4. 编排层写入 `job_raw_records`。
5. 编排层更新采集任务状态并返回入库统计。

能力层爬虫接口不得直接依赖岗位库模型，也不得直接调用 JobService。

## 10. 数据库标准

- PostgreSQL 是当前唯一持久化组件，暂不引入 Redis。
- Agent 相关表放入 `agent` schema。
- 岗位和爬虫相关表当前放入 `public` schema，后续可按需要拆成 `job`、`spider` schema。
- 原始招聘数据必须保留到 `job_raw_records`，方便后续重新分析。
- 聚合岗位画像写入 `job_market_profiles`。
- JSONB 用于保存不稳定结构，例如原始 JSON、模型输出、模板配置。

## 11. 可观测性标准

- 本地服务启动时做 PostgreSQL 健康检查。
- 关键业务流程需要记录日志。
- Agent 调用链路优先接入 LangSmith，用于定位模型调用、工具调用和图状态问题。
- Python 层不强制保留 `request_id`，调用链追踪优先依赖 LangSmith 和服务日志。

## 12. 演进路线

短期：

- 保持能力层和编排层两个 FastAPI 服务独立启动。
- 完善前程无忧采集和原始岗位入库。
- 实现岗位画像生成流程。

中期：

- 为 Agent 增加更多工具和中间件。
- 实现岗位画像版本管理。
- 增加简历分析、职业规划等编排流程。

长期：

- 能力层沉淀为通用 Agent / AI 能力平台。
- 编排层沉淀为就业指导业务智能中台。
- Java 层作为统一业务入口和权限控制层。
