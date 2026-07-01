# MCP设计方案

## 1. 背景

当前平台已经拆分为两个后端：

- `AI-backend`：承载 Agent、模型调用、工具注册、后续知识库等通用 AI 能力。
- `orchestration-backend`：承载就业指导业务编排，例如岗位画像、岗位技能、爬虫数据处理等业务能力。

目前 Agent 使用工具的方式是：在 `AI-backend` 内部把业务接口封装成 LangChain 工具，例如 `search_job_skills`、`create_job_skill`。这种方式在早期实现简单，但后续如果业务工具越来越多，会出现几个问题：

- 工具代码需要写进 `AI-backend`，业务边界会越来越模糊。
- 新增、修改业务工具后，通常需要重启 `AI-backend` 才能生效。
- 工具发现、工具描述、参数 Schema、测试调用缺少统一协议。
- 后续如果其他项目也要复用 Agent 平台，工具接入方式不够标准。

因此需要引入 MCP，将业务能力以标准工具协议暴露给 Agent 平台。

## 2. 目标

MCP 的目标不是为了增加复杂度，而是为了解决工具接入的标准化和热插拔问题。

第一阶段目标：

- 将 `search_job_skills` 和 `create_job_skill` 转换为 MCP 工具。
- Agent 平台可以从 MCP 服务动态发现工具列表。
- Agent 运行时可以调用 MCP 工具，而不是把业务工具硬编码在 `AI-backend` 内部。
- 工具仍然复用 `orchestration-backend` 现有业务接口和数据库逻辑。

后续目标：

- 支持更多业务工具接入，例如岗位画像查询、课程推荐、知识库检索等。
- 支持 MCP 工具热加载或刷新。
- 支持工具管理页面查看 MCP 工具、参数 Schema、调用测试结果。
- 支持不同项目独立注册自己的 MCP 工具服务。

## 3. 两种实现方案对比

### 方案一：使用 fastapi-mcp

`fastapi-mcp` 的思路是：直接把现有 FastAPI 接口转换为 MCP 工具。

优点：

- 接入成本低。
- 可以复用现有 FastAPI 路由。
- 不需要额外写一套 MCP 服务代码。
- 对当前已有接口改造较少。

缺点：

- 工具边界容易和 API 边界混在一起。
- 并不是所有业务 API 都适合作为 Agent 工具暴露。
- 工具名称、工具描述、参数描述可能会受接口设计限制。
- 后续如果需要工具级权限、工具级配置、工具级限流，灵活度可能不足。

适合场景：

- 快速验证 MCP 能力。
- 工具和 API 基本一一对应。
- 对工具描述和调用行为要求不复杂。

### 方案二：使用 FastMCP 单独封装 MCP 服务

`FastMCP` 的思路是：单独启动一个 MCP 服务，在 MCP 工具内部调用 `orchestration-backend` 的业务接口。

优点：

- MCP 工具层和业务 API 层解耦。
- 可以专门为 Agent 设计工具名称、参数、描述和返回结构。
- 可以只暴露适合 Agent 使用的业务能力。
- 后续更容易做工具热加载、工具级配置、工具测试、工具审计。
- 更适合作为通用 Agent 平台的标准工具接入层。

缺点：

- 需要维护一层 MCP 服务代码。
- 部署结构比直接转换 FastAPI 接口多一层。
- 需要处理 MCP 服务到业务服务的 HTTP 调用、错误转换和超时控制。

适合场景：

- 平台后续会有很多工具。
- 工具不一定等于业务 API。
- Agent 平台希望保持通用，不直接耦合具体业务模块。
- 需要工具热插拔、工具管理、工具测试和跨项目复用。

## 4. 推荐方案

推荐使用方案二：基于 FastMCP 单独封装 MCP 服务。

原因：

- 当前平台已经明确拆分为 `AI-backend` 和 `orchestration-backend`，边界应该继续保持清晰。
- `AI-backend` 是通用 AI 能力层，不应该长期内置大量就业业务工具。
- `orchestration-backend` 是业务编排层，业务工具应该由它提供或由贴近它的 MCP 服务封装。
- FastMCP 可以让工具定义更贴近 Agent 使用方式，而不是简单暴露 HTTP API。

第一阶段可以采用“轻量 MCP 服务”模式：

- MCP 服务代码可以先放在 `AI-backend` 中统一启动和管理。
- MCP 工具内部通过 HTTP 调用 `orchestration-backend` 的岗位技能接口。
- 等后续工具数量变多，或者需要独立部署时，再把 MCP 服务拆成独立进程。

也就是说，代码组织上先靠近 `AI-backend`，业务执行仍然落在 `orchestration-backend`。

## 5. 服务边界设计

### AI-backend

负责：

- Agent 运行。
- 模型服务配置。
- 工具注册与工具发现。
- MCP 客户端接入。
- 将 MCP 工具转换为 Agent 可调用工具。

不负责：

- 岗位技能的数据库写入逻辑。
- 岗位画像的业务生成落库逻辑。
- 招聘爬虫和岗位数据处理逻辑。

### orchestration-backend

负责：

- 岗位技能查询与创建。
- 岗位画像生成与保存。
- 岗位数据入库。
- 其他就业指导业务流程。

不负责：

- Agent 运行框架。
- 模型网关调用。
- 通用 Agent 中间件。

### MCP 服务

负责：

- 定义 Agent 可见的工具。
- 将工具参数转换为业务 API 请求。
- 将业务 API 返回转换为 Agent 友好的工具结果。
- 向 `AI-backend` 暴露工具列表和工具调用能力。

## 6. 第一阶段工具设计

### search_job_skills

用途：查询平台技能库中是否存在相关技能。

建议参数：

```json
{
  "keywords": ["FastAPI", "PostgreSQL"]
}
```

返回结果建议：

```json
{
  "items": [
    {
      "keyword": "FastAPI",
      "matches": [
        {
          "skill_id": 1,
          "name": "FastAPI",
          "description": "Python Web API 开发框架"
        }
      ]
    }
  ]
}
```

设计说明：

- `keywords` 使用批量参数，减少模型多次调用工具。
- MCP 工具不直接判断是否同一个技能，只返回候选结果。
- 是否引用已有技能，由 Agent 根据工具结果和岗位语义判断。

### create_job_skill

用途：当技能库中不存在语义相同技能时，由 Agent 创建新技能。

建议参数：

```json
{
  "name": "FastAPI",
  "description": "FastAPI 是一个基于 Python 类型提示构建的高性能 Web API 开发框架。"
}
```

返回结果建议：

```json
{
  "skill_id": 1,
  "name": "FastAPI",
  "description": "FastAPI 是一个基于 Python 类型提示构建的高性能 Web API 开发框架。"
}
```

设计说明：

- 第一阶段只要求 `name` 和 `description`。
- 不做技能别名、分类、向量化、人工审核。
- 后续可以增加 embedding 检索、技能合并、投毒防护等能力。

## 7. Agent 调用链路

第一阶段链路如下：

```text
用户请求
  ↓
AI-backend /agent/run
  ↓
AgentService 组装 Agent
  ↓
ToolService 加载 MCP 工具
  ↓
Agent 判断需要查询技能
  ↓
调用 MCP 工具 search_job_skills
  ↓
MCP 服务调用 orchestration-backend /job/skills/search
  ↓
返回技能候选结果
  ↓
Agent 判断是否需要创建技能
  ↓
调用 MCP 工具 create_job_skill
  ↓
MCP 服务调用 orchestration-backend /job/skills/create
  ↓
返回 skill_id
  ↓
Agent 输出岗位画像 JSON
```

## 8. MCP 服务部署方式

第一阶段建议：MCP 服务和 `AI-backend` 一起启动。

原因：

- 当前工具数量少，单独部署 MCP 服务收益不大。
- `AI-backend` 本身负责 Agent 和工具管理，放在一起便于开发和调试。
- 后续需要独立部署时，可以再把 MCP 服务拆出去。

启动方式可以有两种：

- 方式一：`AI-backend` FastAPI 启动时，同时挂载 MCP HTTP 路由。
- 方式二：`AI-backend` 启动时额外启动一个 MCP 子服务端口。

第一阶段更推荐方式一，减少进程数量。

后续如果 MCP 工具越来越多，或者多个业务系统都要接入，可以改成独立 MCP 服务：

```text
AI-backend
  ↓ MCP Client
MCP Server
  ↓ HTTP
orchestration-backend
```

## 9. 热加载设计

MCP 热加载可以分阶段做。

### 第一阶段：手动刷新

提供一个工具刷新接口，例如：

```text
POST /agent/tools/refresh
```

作用：

- 重新读取 MCP 工具列表。
- 更新 Agent 平台内存中的工具注册表。
- 不需要重启 `AI-backend`。

### 第二阶段：配置驱动

新增 MCP 服务配置表或配置文件，记录：

- MCP 服务名称。
- MCP 服务地址。
- 是否启用。
- 超时时间。
- 工具前缀。

`AI-backend` 启动时加载配置，也可以通过接口刷新。

### 第三阶段：自动发现

后续可以考虑：

- 定时刷新 MCP 工具列表。
- MCP 服务心跳检测。
- 工具版本变化自动更新。

## 10. 工具管理页面设计

工具管理页面后续应支持：

- 查看内置工具和 MCP 工具。
- 区分工具来源：`builtin`、`mcp`。
- 查看工具名称、描述、参数 Schema、返回示例。
- 选择一个工具进行测试调用。
- 展示测试请求体和响应结果。
- 显示工具是否启用。

工具列表返回建议增加字段：

```json
{
  "name": "search_job_skills",
  "description": "查询平台岗位技能库",
  "source": "mcp",
  "server_name": "job-mcp",
  "args_schema": {},
  "enabled": true
}
```

## 11. 和现有 LangChain 工具的关系

短期内可以保留现有内置工具，逐步迁移到 MCP。

迁移策略：

1. 先实现 MCP 版 `search_job_skills` 和 `create_job_skill`。
2. 在测试 Agent 模板中切换使用 MCP 工具。
3. 验证岗位画像生成链路稳定。
4. 再移除 `AI-backend` 中硬编码的岗位技能工具。

这样可以降低一次性切换风险。

## 12. 风险与注意事项

### 工具描述质量

Agent 是否会正确调用工具，很大程度依赖工具描述和参数描述。

要求：

- 工具名称要清晰。
- 工具描述要说明什么时候调用。
- 参数描述要说明字段含义和约束。
- 返回结构要稳定。

### 错误返回

MCP 工具不应该把一大段异常栈直接返回给模型。

建议返回：

```json
{
  "success": false,
  "message": "技能服务暂时不可用",
  "detail": "HTTP 502"
}
```

### 用户投毒

当前阶段先允许 Agent 自动创建技能，但后续需要考虑：

- 重复技能合并。
- 恶意技能名称过滤。
- 技能描述质量校验。
- 技能来源记录。
- 技能变更审计。

### 工具调用循环

如果工具返回不清晰，Agent 可能反复调用工具。

建议：

- 工具返回中明确 `found`、`created`、`items` 等状态。
- Prompt 中明确每个技能最多查询一次，只有不存在时才创建。
- 中间件可以限制同一轮同一工具的重复调用。

## 13. MVP实施计划

第一步：保留现有 job 技能 API。

- `/job/skills/search`
- `/job/skills/create`

第二步：在 `AI-backend` 中新增 MCP 服务模块。

建议目录：

```text
backend/AI-backend/app/server/mcp/
  api/
  src/
    servers/
    tools/
    clients/
    schemas/
```

第三步：实现 job MCP 工具。

- `search_job_skills`
- `create_job_skill`

第四步：让 Agent ToolService 支持 MCP 工具加载。

- 内置工具继续保留。
- MCP 工具作为一种新的工具来源。
- Agent 模板中可以配置是否启用 MCP 工具。

第五步：工具管理页面支持 MCP 工具展示和测试。

第六步：岗位画像生成 Agent 切换到 MCP 工具验证。

## 14. 当前结论

当前阶段不建议直接把所有 FastAPI 接口自动暴露成 MCP 工具。

推荐方案是：

- 使用 FastMCP 封装专门面向 Agent 的 MCP 工具。
- MCP 工具内部调用 `orchestration-backend` 的业务 API。
- MCP 服务第一阶段可以跟随 `AI-backend` 一起启动。
- 后续工具规模变大后，再拆成独立 MCP 服务。

这个方案能兼顾当前开发效率和后续平台扩展性。
