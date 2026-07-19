# Agent 知识库检索接入说明

## 1. 能力定位

知识库检索属于 AI-backend 内部基础能力，不是 MCP 外部工具。

模板的 `tools` 字段继续只保存 MCP 工具编码。知识库能力由模板
`optional_features.knowledge_enabled` 控制，系统在 Agent 组装阶段自动挂载
`search_knowledge_base`。

## 2. 模板配置

```json
{
  "optional_features": {
    "knowledge_enabled": true,
    "knowledge_base_ids": [
      "kb_xxx"
    ]
  }
}
```

- `knowledge_enabled=false`：不向 Agent 注入知识库检索工具。
- `knowledge_enabled=true`：自动注入内部工具。
- `knowledge_base_ids`：Agent 允许访问的知识库白名单，最多 20 个。
- 开启能力后必须至少配置一个知识库。

模型不能传入或修改知识库 ID。白名单会被写入 LangChain Runtime Context，
工具执行时从可信上下文读取。

## 3. 执行链路

```text
Agent 模板
  -> AgentRunLifecycleService 解析模板
  -> AgentRuntimeContext 保存知识库白名单
  -> AgentAssembler 检查 knowledge_enabled
  -> 自动挂载 search_knowledge_base
  -> 模型传入 query 和 top_k
  -> 工具把 knowledge_base_ids 映射为 Milvus Collection
  -> 执行 Hybrid 检索和可选 Rerank
  -> Command 写入 retrieval_context
  -> InjectRetrievalContextMiddleware 按 run_id 过滤
  -> 下一轮模型从系统提示词读取检索证据
```

## 4. 工具参数

模型能看到的参数只有：

```json
{
  "query": "用户要查询的问题",
  "top_k": 5
}
```

`ToolRuntime`、`knowledge_base_ids`、`run_id` 都由 LangGraph 和平台自动注入，
不会暴露为模型工具参数。

## 5. 上下文隔离

检索结果写入 LangGraph state 时携带当前 `run_id`。同一个 `conversation_id`
可以跨轮保留 Checkpoint，但中间件只读取当前运行的检索证据，因此上一轮知识库
结果不会污染下一轮对话。

## 6. 前端配置

1. Agent 模板编辑页提供“挂载知识库”开关。
2. 开启后显示“可访问知识库”多选框。
3. 保存时若未选择知识库，前端会阻止提交。
4. 内部检索工具不会出现在工具管理页或模板 MCP 工具列表中。
