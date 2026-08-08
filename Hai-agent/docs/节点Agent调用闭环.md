# 节点 Agent 调用闭环

## 目标

Hai-agent 负责用户、项目、阶段和分支业务；AI-backend 负责 Agent 组装、模型调用、工具、中间件、Checkpoint 和流式事件。两者通过 HTTP Agent 接口与 MCP 工具形成闭环。

## 完整时序

```text
前端
  -> POST /workflow/nodes/messages
Hai-agent
  -> 校验 JWT 用户和 node_id 归属
  -> 查询项目、节点、agent_id、agent_thread_id
  -> 构造动态 inputs
  -> POST AI-backend /agent/messages
AI-backend
  -> 按 agent_id 加载阶段模板
  -> 使用 inputs 渲染动态提示词
  -> 使用 agent_thread_id 维护当前节点 Checkpoint
  -> 按需读取附件、检索知识库并与用户交互
  -> 调用 save_stage_result
Hai-agent MCP
  -> 从 X-Agent-* 请求头读取节点上下文
  -> 校验用户、项目、分支、节点、阶段和结果版本
  -> 保存 JSON 阶段结果，节点状态更新为 ready
AI-backend
  -> 继续生成最终回复与 SSE 事件
Hai-agent
  -> 将 SSE 原样转发给前端
前端
  -> 节点 ready 后允许用户点击进入下一阶段
  -> POST /workflow/nodes/advance
```

## 动态 Inputs

Hai-agent 不允许前端直接提交 Runtime Context。系统根据数据库中的项目和节点自动生成：

```json
{
  "user_id": "...",
  "project_id": "...",
  "branch_id": "...",
  "node_id": "...",
  "stage_code": "project_preparation",
  "project_context": {},
  "previous_stage_result": {},
  "current_stage_result": {}
}
```

其中前五项供 MCP 拦截器使用，后三项供 Agent 模板动态渲染。前端无法覆盖这些字段。

## 会话和节点边界

- 一个节点固定使用一个 `agent_thread_id`，同一阶段的多轮对话复用该 Checkpoint。
- 进入下一阶段时创建新节点和新 `agent_thread_id`。
- 已完成或已取消节点不能继续发送消息；后续回溯修改应通过新分支完成。
- Agent 执行前只做无锁读取，完成上下文复制后结束数据库读取事务，避免长时间 SSE 占用事务。

## 流式与非流式

- `stream=true`：Hai-agent 返回 `text/event-stream`，保持 AI-backend 的事件类型和 data 不变。
- `stream=false`：Hai-agent 返回统一 `{code,msg,data}`，data 包含 node_id、agent_id、conversation_id、run_id、answer 和 tool_results。
- 上游 SSE 建立失败时，Hai-agent 会返回 `event=error` 的流式错误事件，而不会伪造 Agent 成功结果。

## 启动前检查

1. AI-backend 已启动且 `AI_BACKEND_BASE_URL` 可访问。
2. 五个阶段模板已经从 `agent_configs` 导入 AI-backend。
3. AI-backend 已同步 Hai-agent MCP 服务，并使用工具编码 `hai.save_stage_result`。
4. 模板引用的 `chat_main` 模型配置存在并启用。
5. 需要知识库的阶段调用时传入允许访问的 `knowledge_base_ids`。
