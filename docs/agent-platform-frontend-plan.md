# Agent 管理平台前端页面规划

> 基于 `capability-backend` 现有接口梳理，涵盖 **10 个核心页面**，按优先级排序。

---

## 📋 页面规划总览

| # | 页面 | 路由 | 核心功能 |
|---|---|---|---|
| 1 | **Dashboard 首页** | `/` | 系统总览 + 运行统计 |
| 2 | **Agent 模板管理** | `/agents` | CRUD + 配置 |
| 3 | **Agent 模板编辑** | `/agents/:agent_id/edit` | 完整配置表单 |
| 4 | **Agent 试跑台** | `/agents/:agent_id/playground` | 在线调试 |
| 5 | **会话历史** | `/conversations` | 会话列表 |
| 6 | **会话详情** | `/conversations/:id` | 消息流 + 运行记录 |
| 7 | **Agent 运行监控** | `/runs` | 运行记录 + 链路追踪 |
| 8 | **工具管理** | `/tools` | 工具注册 + 调试 |
| 9 | **模型配置** | `/settings/model` | 网关配置展示 |
| 10 | **A2A 可视化** | `/a2a` | Agent 调用关系拓扑图 |

---

## 🏠 1. Dashboard 首页

**路由**: `/`

**功能**:
- 系统健康状态（Agent 服务 / PostgreSQL / 模型网关）
- **今日 / 本周 Agent 运行统计**：总调用量 / 成功率 / 平均耗时
- 最近运行的 Agent 任务（最近 5 条）
- 快捷入口：新建 Agent / 进入 Playground / 查看运行监控

**调用的后端接口**:
```http
GET  /agent/health
GET  /agent/capabilities
POST /agent/runs/search     # 查最近运行记录用于 Dashboard 展示
```

**Dashboard 运行统计 Request**:
```json
{
  "page": 1,
  "page_size": 5
}
```

---

## 🤖 2. Agent 模板管理列表页

**路由**: `/agents`

**功能**:
- 分页展示所有 Agent 模板
- 支持关键字搜索（agent_id / agent_name / description）
- 支持状态筛选（active / disabled）
- 快捷操作：编辑 / 克隆 / 删除 / 进入 Playground

**调用的后端接口**:
```http
POST /agent/templates/search
```

**Request 示例**:
```json
{
  "keyword": "job",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

**Response 字段**:
| 字段 | 说明 |
|---|---|
| `total` | 总数 |
| `items[].agent_id` | Agent 唯一 ID |
| `items[].agent_name` | 展示名称 |
| `items[].description` | 描述 |
| `items[].status` | 状态（active / disabled） |
| `items[].config.tools` | 绑定工具列表 |
| `items[].config.is_sub_agent` | 是否可 A2A 调用 |
| `items[].created_at` / `updated_at` | 时间戳 |

---

## ✏️ 3. Agent 模板编辑页

**路由**: `/agents/create` 或 `/agents/:agent_id/edit`

**功能**（完整配置表单）:

| 分区 | 字段 | 说明 |
|---|---|---|
| **基本信息** | agent_id | 唯一标识（创建后不可改） |
| | agent_name | 展示名称 |
| | description | 描述 |
| | status | active / disabled |
| **Prompt 配置** | system_prompt | 系统提示词（富文本） |
| | response_format | JSON Schema 结构化输出 |
| **工具配置** | tools | 多选工具（从 `/agent/capabilities` 获取） |
| **模型配置** | model | 模型别名 |
| | temperature | 采样温度（0~2） |
| | timeout_seconds | 超时时间（秒） |
| | max_retries | 最大重试次数 |
| **可选能力** | long_term_memory_enabled | 长期记忆开关 |
| | is_sub_agent | 是否可被 A2A 调用 |
| **A2A 配置** | sub_agent_list | 可调用的子 Agent 列表（多选） |

**调用的后端接口**:
```http
POST /agent/templates/upsert          # 创建或更新
POST /agent/templates/detail           # 查询详情（编辑时加载）
GET  /agent/capabilities              # 获取注册工具列表
POST /agent/templates/search          # 获取 sub_agent_list 下拉选项
```

---

## 🧪 4. Agent Playground 试跑台

**路由**: `/agents/:agent_id/playground`

**功能**:
- **左侧面板**：Agent 配置展示（只读），展示 system_prompt / tools / model 等
- **右侧对话区**：
  - 输入框（模拟用户 query）
  - conversation_id 输入（可空，自动生成 UUID）
  - 可视化选择本次开启的工具（覆盖模板默认）
  - 开启 / 关闭流式输出（stream toggle）
  - 可选能力开关（long_term_memory 等）
- **下方**：消息流展示（支持流式 SSE 渲染）
- **底部**：结构化输出 JSON 展示（如果有 response_format）

**调用的后端接口**:
```http
POST /agent/run        # 非流式 or 流式 SSE
GET  /agent/capabilities
```

**Request 示例**（Playground 调试）:
```json
{
  "query": "帮我查询岗位技能：Python",
  "conversation_id": "user_123_session_456",
  "stream": true,
  "tools": ["search_job_skills", "create_job_skill"],
  "optional_features": {
    "long_term_memory_enabled": false
  }
}
```

---

## 💬 5. 会话历史列表页

**路由**: `/conversations`

**功能**:
- 按 conversation_id 精确搜索会话
- 展示会话列表（conversation_id / 标题 / 状态 / 时间）
- 点击进入会话详情

**调用的后端接口**:
```http
POST /conversations/search
```

> ⚠️ **当前限制**：接口入参只有 `conversation_id` 精确匹配，还不支持"我的所有会话"查询。如果需要真正的会话列表，后端需要扩展增加 `user_id / keyword / page` 等过滤条件。

---

## 📜 6. 会话详情页

**路由**: `/conversations/:conversation_id`

**功能**:
- **上方 Tab 切换**：
  - `消息流` — 完整历史对话（从旧到新）
  - `运行记录` — 该会话下所有 Agent 运行（来自 `agent_runs` 表）
- **消息流 Tab**：
  - 每条消息标注：role / type / tool_name / content
  - 工具调用可展开查看 `structured_content`（工具参数 / 返回值）
  - 支持翻页（如果历史超过 limit 200）
  - 复盘按钮：重新带入这个 conversation_id 进入 Playground
- **运行记录 Tab**：
  - 展示该会话下所有主 Agent 运行（run_type=main）
  - 每条记录展示：run_id / agent_id / status / elapsed_ms / started_at
  - 点击 run_id → 跳转 `/runs/:run_id` 查看详情和链路

**调用的后端接口**:
```http
POST /conversations/messages          # 获取消息列表
POST /conversations/search            # 获取会话元信息（标题/状态）
POST /agent/runs/search               # 获取该会话下所有运行记录
```

**Request 示例**（运行记录）:
```json
{
  "conversation_id": "user_123_session_456",
  "run_type": "main",
  "page": 1,
  "page_size": 50
}
```

---

## 📊 7. Agent 运行监控页 ⭐ 新增

**路由**: `/runs`

**功能**:

- **顶部统计卡片**：今日/本周/本月运行总量 / 成功率 / 失败数 / 平均耗时
- **左侧筛选面板**：
  - run_id 精确搜索
  - run_type：main / sub（全选 / 仅主 Agent / 仅子 Agent）
  - agent_id：Agent 模板筛选
  - status：running / success / failed
  - 时间范围：started_at 区间
- **右侧运行记录列表**：
  - 分页展示（默认按 started_at 降序）
  - 每行展示：run_id / run_type / agent_id / status / elapsed_ms / started_at
  - status 颜色标记：running=蓝色 / success=绿色 / failed=红色
  - 操作：查看详情 / 查看链路（仅 main）/ 重新带入 Playground
- **底部链路展开**（点击"查看链路"）：
  - 树形结构展示主子 Agent 调用链
  - 主 Agent run_id（根节点）
  - 子 Agent run_id（子节点，标注 parent_run_id）
  - 每节点展示：query / answer / status / elapsed_ms
  - 支持展开/收起

**调用的后端接口**:
```http
POST /agent/runs/search      # 分页查询运行记录（支持多条件筛选）
POST /agent/runs/detail     # 查询单条运行详情
POST /agent/runs/chain      # 查询主子运行链路
```

**Request 示例**（分页查询）:
```json
{
  "run_type": "main",
  "status": "failed",
  "page": 1,
  "page_size": 20
}
```

**Response 字段**:
| 字段 | 说明 |
|---|---|
| `total` | 总数量 |
| `items[].run_id` | 运行 ID |
| `items[].run_type` | main=主 Agent，sub=子 Agent |
| `items[].parent_run_id` | 父级运行 ID（子 Agent 有值） |
| `items[].agent_id` | 调用的 Agent 模板 ID |
| `items[].conversation_id` | 所属会话 ID |
| `items[].query` | 运行输入 |
| `items[].answer` | 运行输出 |
| `items[].status` | running / success / failed |
| `items[].error_message` | 失败原因 |
| `items[].elapsed_ms` | 运行耗时（毫秒） |
| `items[].started_at` / `finished_at` | 时间戳 |

**链路查询 Response**（`/runs/chain`）:
```json
{
  "run_id": "主Agent_run_id",
  "items": [
    { "run_id": "AAA", "run_type": "main", "query": "...", "status": "success" },
    { "run_id": "BBB", "run_type": "sub", "parent_run_id": "AAA", "query": "...", "status": "success" },
    { "run_id": "CCC", "run_type": "sub", "parent_run_id": "AAA", "query": "...", "status": "failed" }
  ]
}
```

---

## 🔧 8. 工具管理页

**路由**: `/tools`

**功能**:
- 展示所有已注册工具（从 `/agent/capabilities` 获取 `registered_tools`）
- 每个工具卡片展示：
  - 工具名称
  - 工具描述
  - 所属分组（job_tools 等）
- 工具调试区（输入参数 → 发起调用 → 查看结果）

**调用的后端接口**:
```http
GET /agent/capabilities       # 获取 registered_tools 列表
```

---

## ⚙️ 9. 模型配置页

**路由**: `/settings/model`

**功能**:
- 展示当前模型网关配置（只读）
  - gateway_path（YAML 路径）
  - provider / base_url
  - chat_model / embedding_model
  - 可用模型别名列表
  - LangSmith 集成状态
- 展示 API Key 配置状态（已配置 / 未配置）

**调用的后端接口**:
```http
GET /agent/model/config
```

**Response 字段**:
```json
{
  "gateway_path": "...",
  "available_models": ["gpt-4o", "gpt-4o-mini"],
  "provider": "openai",
  "chat_model": "gpt-4o",
  "has_api_key": true,
  "langsmith_tracing": false
}
```

---

## 🔗 10. A2A 可视化页

**路由**: `/a2a`

**功能**（基于你们讨论的 A2A 架构）:
- 拓扑图展示所有 Agent 及其 A2A 调用关系
- 每个节点：Agent 名称 / is_sub_agent 标记
- 每条边：sub_agent_list 关系
- 点击节点 → 跳转该 Agent 的编辑页

**数据来源**:
```http
POST /agent/templates/search    # 拉全部 active Agent，解析 config.is_sub_agent + config.a2a
```

---

## 📊 页面优先级建议

| 优先级 | 页面 | 理由 |
|---|---|---|
| 🔴 P0 | Agent 模板管理 + Playground | 核心功能，最快验证 Agent 能力 |
| 🟡 P1 | 会话详情 + **运行监控** | 调试闭环 + 链路追踪必备 |
| 🟢 P2 | 会话列表 + Dashboard | 运营视角 |
| 🔵 P3 | 工具管理 + 模型配置 + A2A 可视化 | 运维 / 高级功能 |

---

## 🎯 核心数据流：运行链路追踪

```
用户发起请求
     │
     ▼
┌──────────────────────────────────────────────────┐
│  /agent/run  (主 Agent)                          │
│  run_id = "AAA-001"                              │
│  status: running → success                       │
└──────────────────────────────────────────────────┘
     │
     ├── A2A 调用子 Agent
     ▼
┌──────────────────────────────────────────────────┐
│  子 Agent run_id = "BBB-001"                     │
│  parent_run_id = "AAA-001"                       │
│  run_type = "sub"                                │
└──────────────────────────────────────────────────┘
     │
     └── A2A 调用子 Agent
         ▼
┌──────────────────────────────────────────────────┐
│  子 Agent run_id = "CCC-001"                     │
│  parent_run_id = "AAA-001"                       │
│  run_type = "sub"                                │
└──────────────────────────────────────────────────┘

前端展示：
/runs                    → 看到 AAA-001 / BBB-001 / CCC-001 三条记录
/runs/:AAA-001/chain     → 看到完整的主子调用树
```

---

## ⚠️ 后端待优化项（前端依赖）

| 问题 | 影响页面 | 建议 |
|---|---|---|
| `conversations/search` 只支持精确查一个 ID | 会话列表页无法真正使用 | 扩展增加 `user_id / keyword / page` 参数 |
| 工具参数 Schema 未暴露 | 工具管理页调试区无法动态渲染表单 | `/agent/capabilities` 需返回工具的 `args_schema` |
| Agent 克隆接口缺失 | 模板管理无法快速复制 | 新增 `POST /agent/templates/clone` |
| 会话消息 limit 上限 200 | 极长对话拿不到完整历史 | 支持 offset 分页 |
| 运行统计无独立聚合接口 | Dashboard 统计需前端手动计算 | 新增 `/agent/runs/statistics` 返回聚合数据 |

---

## 🎨 技术栈建议

| 层 | 推荐方案 |
|---|---|
| 框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5（企业级，组件丰富） |
| 状态管理 | Zustand（轻量）或 React Query（API 状态） |
| 路由 | React Router v6 |
| SSE 流式渲染 | EventSource + fetch ReadableStream |
| 拓扑图（A2A） | React Flow 或 AntV G6 |
| 运行链路树 | Ant Design Tree + 自定义展开组件 |
| 发起后端请求 | Axios + 统一拦截器 |
