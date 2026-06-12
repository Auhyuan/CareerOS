# Agent 构建模式说明

## 文档目标

本文档说明平台 Agent 从接口调用到最终回复的完整生命周期。

它重点回答几个问题：

- `/agent/run` 被调用后发生了什么。
- 一个 Agent 是如何被组装出来的。
- 哪些逻辑属于 Agent 构建。
- 哪些逻辑属于本次运行上下文。
- `create_agent` 在整个链路中扮演什么角色。
- Agent 如何执行、保存历史、返回结果。

这份文档用于保护 Agent 层的边界，避免后续业务开发时把岗位画像、知识库、任务编排等逻辑都堆进 `AgentService`。

## 总体生命周期

一次 Agent 调用的完整生命周期如下：

```text
HTTP 请求
  -> agent_api.py
  -> AgentRunRequest
  -> AgentService.run()
  -> 构建 runtime context
  -> 按需读取会话历史
  -> assemble_agent()
  -> create_agent()
  -> agent.ainvoke()
  -> 提取模型回复
  -> 按需写入会话历史
  -> AgentRunResponse
  -> Result.success()
  -> HTTP 响应
```

更细一点：

```text
1. 接口接收请求
2. 请求参数校验
3. 构建本次运行上下文
4. 处理会话上下文
5. 生成 Agent 装配配置
6. 渲染 system prompt
7. 加载工具
8. 构建 context_schema
9. 加载 middleware
10. 识别 middleware state_schema
11. 获取 checkpointer
12. 调用 create_agent
13. 组装输入 messages
14. 执行 agent.ainvoke
15. 提取最终回答
16. 处理记忆占位逻辑
17. 保存用户消息和 Agent 回复
18. 返回统一响应
```

## 接口入口

当前 Agent 运行入口是：

```text
POST /agent/run
```

对应文件：

```text
backend/app/server/agent/api/agent_api.py
```

接口层职责很轻，只做三件事：

```text
1. 接收 AgentRunRequest
2. 获取数据库 Session
3. 调用 AgentService.run()
```

接口层不应该写 Agent 装配逻辑，也不应该写具体业务逻辑。

## 请求对象

`/agent/run` 使用 `AgentRunRequest` 作为请求体。

它包含几类信息：

```text
基础身份：
  agent_id
  conversation_id
  request_id

用户输入：
  query
  input_messages
  files

业务变量：
  inputs

工具控制：
  tools

能力开关：
  optional_features

模型参数：
  runtime_options

调试参数：
  dry_run
```

需要注意：`AgentRunRequest` 是 API 请求模型，不应该直接等同于 Agent 内部装配模型。

因此我们会把它转换成内部使用的 `AgentBuildConfig`。

## 第一阶段：构建 Runtime Context

进入 `AgentService.run()` 后，第一步是：

```python
context = self.runtime_context_service.build_context(request)
```

Runtime context 表示本次调用的外部业务上下文。

它不是 prompt，也不是 messages。

它主要给工具、中间件、LangChain runtime 使用。

典型内容包括：

```text
agent_id
thread_id
request_id
allowed_tools
inputs
metadata
optional_features
```

例如：

```json
{
  "agent_id": "job_profile_agent",
  "thread_id": "conversation_001",
  "inputs": {
    "job_direction": "AI应用开发",
    "knowledge_base_id": "kb_001"
  }
}
```

这些参数可以被工具读取，但不一定要展示给模型。

## 第二阶段：处理会话上下文

如果请求中开启了：

```json
{
  "optional_features": {
    "conversation_context_enabled": true
  }
}
```

那么 `AgentService.run()` 会处理会话上下文。

主要流程：

```text
1. 根据 conversation_id/thread_id 确保会话存在。
2. 从 agent_messages 中读取最近历史消息。
3. 把数据库消息转换成 LangChain messages。
4. 后续与本轮用户消息一起传给 Agent。
```

对应逻辑属于 `ContextService`，不属于 Agent 构建。

原因是：

```text
Agent 构建负责“这个 Agent 具备什么能力”。
会话上下文负责“这次调用发生在哪条会话线上”。
```

同一个 Agent 可以用于有会话的对话，也可以用于无会话的定时任务或离线分析。

## 第三阶段：生成 Agent 装配配置

Agent 构建从这里开始：

```python
build_config = self.build_agent_assembly_config(request)
```

`build_agent_assembly_config()` 的职责是把 API 请求转换成内部装配配置。

它主要决定：

```text
使用哪个 agent_id
使用哪段 system_prompt
允许使用哪些工具
启用哪些内部能力
是否启用 checkpointer
是否启用长期记忆
是否启用延迟工具筛选
```

这里会把：

```python
request.optional_features
```

转换成：

```python
AgentFeatureConfig
```

这样做的好处是：

```text
API 层面对的是业务可理解的能力开关。
Agent 内部面对的是装配需要的技术配置。
```

## 第四阶段：渲染 System Prompt

接下来会渲染系统提示词：

```python
system_prompt = self.prompt_service.render_system_prompt(
    build_config.system_prompt,
    context.inputs,
)
```

PromptService 的职责是：

```text
1. 接收基础 prompt。
2. 接收业务变量。
3. 渲染出最终 system prompt。
```

例如基础 prompt 中有：

```text
你是一个 {{job_direction}} 岗位分析专家。
```

`context.inputs` 中有：

```json
{
  "job_direction": "AI应用开发"
}
```

最终可以渲染成：

```text
你是一个 AI应用开发 岗位分析专家。
```

后续接入 Agent 模板后，system prompt 可以来自模板配置。

## 第五阶段：加载工具

工具加载通过：

```python
tools = self.tool_service.get_tools(build_config.tool_names)
```

`build_config.tool_names` 是本次允许使用的工具白名单。

工具层职责是：

```text
1. 注册平台可用工具。
2. 根据工具名筛选本次可用工具。
3. 后续支持工具分类、工具注入参数、MCP 工具、业务工具。
```

模型只能调用本次被加载的工具。

例如岗位画像 Agent 后续可能加载：

```text
query_job_postings
load_job_descriptions
save_job_market_profile
```

知识库 Agent 后续可能加载：

```text
retrieve_knowledgebase_chunks
retrieve_knowledgebase_full_content
```

## 第六阶段：构建 Context Schema

接下来会构建 LangChain runtime context schema：

```python
context_schema = self.runtime_context_service.get_context_schema()
```

`context_schema` 定义的是 runtime context 的结构。

它告诉 LangChain：

```text
本次运行传入的 context 有哪些字段。
工具和中间件可以安全读取哪些上下文数据。
```

例如工具可以从 runtime context 里拿：

```python
runtime.context.inputs.get("knowledge_base_id")
```

这类参数不需要模型自己提供。

## 第七阶段：加载 Middleware

Middleware 通过工厂创建：

```python
middlewares = self.middleware_factory.build_langchain_middlewares(build_config.features)
```

Middleware 是 Agent 的横切能力。

它可以拦截：

```text
模型调用前
模型调用后
工具调用前
工具调用后
Agent 执行前后
```

当前基础中间件包括：

```text
ToolErrorHandlerMiddleware
ToolArgsInjectMiddleware
ToolLoggingMiddleware
MemoryPlaceholderMiddleware
```

这些中间件由 `AgentFeatureConfig` 决定是否启用。

基础能力可以默认启用。

可选能力通过 `optional_features` 控制。

## 第八阶段：识别 State Schema

每个 middleware 可以声明自己的 LangGraph state：

```python
class ToolLoggingMiddleware(AgentMiddleware[CareerAgentState]):
    state_schema = CareerAgentState
```

`create_agent` 会读取这些 `state_schema`，并合并到底层 LangGraph state 中。

当前项目的基础 state 是：

```python
class CareerAgentState(AgentState, total=False):
    tool_trace: NotRequired[list[dict[str, Any]]]
    structured_output: NotRequired[dict[str, Any]]
    profile_draft: NotRequired[dict[str, Any]]
    metadata: NotRequired[dict[str, Any]]
```

这表示 Agent 在运行过程中可以保存：

```text
工具轨迹
结构化输出
岗位画像草稿
运行元信息
```

后续岗位画像 Agent 可以扩展：

```python
class JobProfileState(CareerAgentState, total=False):
    job_postings_context: NotRequired[str]
    source_job_ids: NotRequired[list[int]]
    extracted_requirements: NotRequired[list[dict[str, Any]]]
```

## 第九阶段：获取 Checkpointer

如果启用了 checkpoint：

```python
checkpointer = await self.checkpoint_service.get_checkpointer()
```

checkpointer 负责持久化 LangGraph state。

当前使用 PostgreSQL。

需要区分：

```text
checkpointer 保存 LangGraph state。
ContextService 保存业务会话历史。
```

也就是说：

```text
checkpointer 关心图执行状态。
ContextService 关心用户和 Agent 说过什么。
```

## 第十阶段：调用 create_agent

最终通过 LangChain 的 `create_agent` 创建 Agent：

```python
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    context_schema=context_schema,
    middleware=middlewares,
    checkpointer=checkpointer,
)
```

这些参数分别表示：

```text
model:
  Agent 使用哪个模型思考。

tools:
  Agent 可以调用哪些工具。

system_prompt:
  Agent 的角色、目标、约束。

context_schema:
  runtime context 的结构定义。

middleware:
  模型和工具调用链路上的横切能力。

checkpointer:
  LangGraph state 的持久化组件。
```

`create_agent` 底层会创建 LangGraph 执行图。

我们没有手写完整 `StateGraph`，但仍然使用了 LangGraph 的能力。

## 第十一阶段：组装输入 Messages

Agent 创建完成后，开始准备本次执行输入：

```python
input_messages = [
    *history_messages,
    {"role": "user", "content": request.query},
]
```

如果开启会话上下文，则 `history_messages` 来自数据库。

如果没有开启会话上下文，则只包含本轮用户问题。

注意：

```text
messages 是给模型看的对话内容。
runtime context 是给工具和中间件看的业务上下文。
LangGraph state 是图执行过程中的内部状态。
```

三者不要混用。

## 第十二阶段：写入用户消息

如果开启会话上下文，会在模型调用前写入用户消息：

```text
ContextService.add_user_message()
```

这样即使后续排查，也能看到本次用户输入。

当前写入的是业务历史表，不是 LangGraph checkpoint 表。

## 第十三阶段：执行 Agent

真实执行发生在：

```python
result = await assembly.agent.ainvoke(
    {"messages": input_messages},
    config={
        "configurable": {
            "thread_id": context.thread_id
        },
        "recursion_limit": 50,
    },
    context=context.to_langchain_context(),
)
```

这里有三个关键输入。

### messages

```python
{"messages": input_messages}
```

这是模型能看到的对话消息。

### config

```python
config={"configurable": {"thread_id": context.thread_id}}
```

`thread_id` 用于 LangGraph checkpointer。

同一个 `thread_id` 下，LangGraph 可以保存和恢复 state。

### context

```python
context=context.to_langchain_context()
```

这是传给 runtime 的业务上下文。

工具和中间件可以读取它。

## 第十四阶段：模型和工具循环

`agent.ainvoke()` 内部会进入 LangGraph 执行流程。

大致过程：

```text
1. 模型读取 messages 和 system prompt。
2. 模型决定是否调用工具。
3. 如果调用工具，进入工具节点。
4. middleware 可以拦截工具调用。
5. 工具返回 ToolMessage 或 Command(update=...)。
6. 如果 state 被更新，LangGraph 合并 state。
7. 模型进入下一轮调用。
8. middleware 可以在下一轮模型调用前注入 prompt。
9. 模型输出最终回答。
```

例如知识库检索模式：

```text
工具检索到资料
  -> Command(update={"retrieval_context": "..."})
  -> ToolMessage("工具调用完成")
  -> middleware 下一轮读取 retrieval_context
  -> 注入 system prompt
  -> 模型基于资料回答
```

这就是 `create_agent + middleware + state + Command(update)` 的核心模式。

## 第十五阶段：提取最终回答

Agent 执行结束后，返回结果中通常包含 `messages`。

当前实现从最后一条消息中提取回答：

```python
answer = result["messages"][-1].content if result.get("messages") else ""
```

后续如果启用结构化输出，也可以从：

```text
structured_response
structured_output
```

中读取结构化结果。

## 第十六阶段：处理长期记忆

当前会调用：

```python
await self.memory_service.save_interaction(context, answer)
```

目前 `MemoryService` 还是占位实现。

后续可以在这里扩展：

```text
长期用户偏好
任务记忆
画像记忆
自动摘要
```

需要注意：

```text
会话上下文不是长期记忆。
会话上下文由 ContextService 管理。
长期记忆由 MemoryService 管理。
```

## 第十七阶段：写入 Agent 回复

如果开启会话上下文，会写入 Agent 回复：

```text
ContextService.add_assistant_message()
```

写入内容包括：

```text
conversation_id
assistant content
request_id
agent_id
metadata
```

这样后续可以通过：

```text
POST /agent/conversations/messages
```

查询会话历史。

## 第十八阶段：返回响应

最后返回：

```python
AgentRunResponse(
    answer=answer,
    structured_output=...,
    metadata=assembly.metadata,
)
```

API 层再包装成统一响应：

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "answer": "...",
    "structured_output": {},
    "metadata": {}
  }
}
```

## Agent 构建和运行的边界

### 属于 Agent 构建的内容

这些属于 `assemble_agent()`：

```text
模型
工具
system prompt
context_schema
middlewares
state_schema
checkpointer
create_agent
```

它回答的是：

```text
这个 Agent 具备什么能力？
这个 Agent 如何运行？
```

### 不属于 Agent 构建的内容

这些不属于 `assemble_agent()`：

```text
创建会话
读取历史消息
写入用户消息
写入 Agent 回复
接口返回包装
业务数据库查询
岗位画像结果落库
```

它们属于运行编排、上下文管理或业务服务。

## build_context 为什么不属于 Agent 构建

`build_context` 构建的是本次请求的运行上下文。

它描述的是：

```text
这一次调用是谁发起的？
这一次使用哪个 conversation_id？
这一次有哪些业务变量？
这一次允许哪些工具？
```

同一个 Agent，可以在不同上下文中运行。

因此 context 是运行实例级别的数据，不是 Agent 能力本身。

## ensure_conversation 为什么不属于 Agent 构建

`ensure_conversation` 是业务会话管理。

它描述的是：

```text
数据库里有没有这条 conversation？
如果没有，要不要创建？
```

这和 Agent 具备什么能力无关。

例如定时任务 Agent 可以没有对话历史，但仍然可以使用同一套 Agent 构建逻辑。

## dry_run 的位置问题

当前 `AgentRunRequest` 里还有 `dry_run`。

它的作用是只返回装配信息，不真实调用模型。

这对调试有用，但它更像诊断能力，不太适合长期放在正式 `/agent/run` 请求里。

后续建议拆成独立接口：

```text
POST /agent/inspect
```

或者：

```text
POST /agent/assembly/preview
```

这样 `/agent/run` 只负责真实运行。

## 模板如何参与构建

当前已经有 Agent 模板表和模板 API。

后续推荐流程：

```text
1. /agent/run 传入 agent_id
2. AgentService 根据 agent_id 查询 agent_templates
3. 读取模板 config
4. 将模板配置和请求参数合并
5. 生成 AgentBuildConfig
6. 调用 assemble_agent
```

模板适合提供默认值：

```text
默认 system_prompt
默认 tools
默认 optional_features
默认 runtime_options
默认业务配置
```

请求参数适合做本次覆盖：

```text
本次 query
本次 conversation_id
本次 inputs
本次临时工具白名单
本次模型参数覆盖
```

## 岗位画像 Agent 如何复用构建模式

岗位画像 Agent 不应该重写一套 Agent 基础设施。

它应该复用通用 Agent 构建模式，只扩展业务层能力。

推荐方式：

```text
1. 定义 JobProfileState
2. 定义岗位数据查询工具
3. 工具返回 Command(update=...)
4. 定义 JobProfilePromptMiddleware
5. 中间件读取 state 并注入岗位数据
6. 模型生成岗位画像
7. 保存岗位画像到 job_market_profiles
```

例如：

```text
query_job_postings 工具
  -> 查询 job_postings
  -> 整理 JD 原文
  -> 写入 state.job_postings_context
  -> ToolMessage 返回“岗位数据读取完成”

JobProfilePromptMiddleware
  -> 读取 state.job_postings_context
  -> 注入 system prompt
  -> 模型生成岗位画像
```

## 当前实现状态

当前已经完成：

```text
AgentRunRequest
AgentService.run
AgentService.assemble_agent
AgentBuildConfig
ModelService
ToolService 基础注册
PromptService
RuntimeContextService
MiddlewareFactory
CareerAgentState
PostgreSQL Checkpointer
ContextService 会话历史
TemplateService 模板 CRUD
```

当前还没有完成：

```text
模板配置自动合并到 /agent/run
业务工具 Command(update=...) 写 state
业务中间件从 state 注入 prompt
岗位画像 Agent 编排
知识库检索工具
长期记忆真实实现
独立 inspect 接口
流式输出
执行轨迹查询
```

## 推荐后续改造顺序

建议按下面顺序推进：

```text
1. 新增 /agent/inspect，替代 run 里的 dry_run。
2. 实现 agent_id 查询模板，并合并模板配置。
3. 实现岗位数据查询工具。
4. 定义 JobProfileState。
5. 工具通过 Command(update=...) 写入岗位数据 state。
6. 实现 JobProfilePromptMiddleware。
7. 实现岗位画像生成接口。
8. 增加 Agent 执行轨迹查询。
9. 再考虑长期记忆和流式输出。
```

## 设计原则

Agent 构建模式需要遵守这些原则：

```text
AgentService 负责编排，不写具体业务算法。
ModelService 负责模型实例创建。
ToolService 负责工具注册和筛选。
PromptService 负责 prompt 渲染。
RuntimeContextService 负责运行上下文。
MiddlewareFactory 负责中间件装配。
ContextService 负责业务会话历史。
CheckpointService 负责 LangGraph state 持久化。
TemplateService 负责 Agent 默认配置。
业务模块通过工具、state、middleware 扩展 Agent。
```

一句话总结：

```text
Agent 构建负责能力装配。
Agent 运行负责本次调用编排。
业务工具负责获取和保存业务数据。
middleware 负责控制模型调用链路。
state 负责保存执行中间结果。
context 负责传递外部业务参数。
```
