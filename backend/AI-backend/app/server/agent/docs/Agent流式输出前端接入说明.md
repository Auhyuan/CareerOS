# Agent 流式输出前端接入说明

本文档说明前端如何接入 `POST /agent/run` 的 SSE 流式输出。

## 一、接口说明

### 请求地址

```http
POST /agent/run
```

### 请求方式

流式接口使用 `POST + text/event-stream`。

由于请求体需要传入 `query`、`agent_id`、`conversation_id` 等 JSON 参数，前端不建议使用原生 `EventSource`，而应使用 `fetch + ReadableStream` 读取 SSE。

### 请求示例

```json
{
  "query": "帮我根据这段 JD 生成岗位画像...",
  "agent_id": "job-profile-agent",
  "conversation_id": "TEST6",
  "stream": true,
  "inputs": {},
  "files": [],
  "optional_features": {
    "long_term_memory_enabled": false
  }
}
```

如果传入 `agent_id`，后端会以 Agent 模板配置为主。前端不需要额外传 `system_prompt`、`tools`、`runtime_options`，除非确实要临时运行非模板 Agent。

## 二、SSE 返回格式

后端每条 SSE 事件格式如下：

```text
event: model_delta
data: {"type":"model_delta","data":{"content":"你好"}}

```

前端应以空行 `

` 拆分事件块，再解析其中的 `event:` 和 `data:`。

`data` 内部始终是 JSON，格式统一为：

```ts
interface AgentSseEvent<T = unknown> {
  type: string
  data: T
}
```

其中 `type` 与 SSE 的 `event:` 一致。

## 三、事件类型

### 1. run_start

表示本次 Agent 运行开始。

```json
{
  "type": "run_start",
  "data": {
    "run_id": "3bef498aafdb403fb2b3692562d06018",
    "thread_id": "TEST6",
    "persistent_conversation": true,
    "stream": true
  }
}
```

前端建议：

- 创建一条新的运行记录。
- 开启 loading 状态。
- 保存 `run_id`，后续可用于查询运行链路。

### 2. agent_assembled

表示 Agent 已完成组装，模型、工具、中间件等已经就绪。

```json
{
  "type": "agent_assembled",
  "data": {
    "run_id": "xxx",
    "model_code": "chat_main",
    "tool_count": 2,
    "tools": ["job.search_job_skills", "job.create_job_skill"],
    "middlewares": ["ToolLoggingMiddleware"],
    "checkpointer_enabled": true
  }
}
```

前端建议：

- 可在调试面板展示。
- 普通聊天界面可以忽略。

### 3. reasoning_delta

模型思考过程增量输出。

```json
{
  "type": "reasoning_delta",
  "data": {
    "content": "我需要先识别岗位职责和技能关键词..."
  }
}
```

前端建议：

- 追加到“思考过程”区域。
- 可以默认折叠，也可以用灰色文本展示。
- 不要把它合并到最终回答正文里。

### 4. model_delta

Agent 正式回复正文增量输出。

```json
{
  "type": "model_delta",
  "data": {
    "content": "岗位画像已生成..."
  }
}
```

前端建议：

- 追加到当前 assistant 消息正文。
- 这是用户最终可见回答的主要来源。
- 流式模式下后端不再额外发送 `final` 事件，最终正文由前端累计 `model_delta` 得到。

### 5. tool_call

模型准备调用工具。

```json
{
  "type": "tool_call",
  "data": {
    "tool_name": "search_job_skills",
    "args": {
      "keywords": ["Python", "FastAPI"]
    },
    "id": "call_xxx",
    "metadata": {
      "langgraph_node": "model",
      "langgraph_step": 2
    }
  }
}
```

前端建议：

- 可展示为“正在调用工具：search_job_skills”。
- 普通聊天正文不要展示工具参数。
- 调试面板可以展示 `args` 和 `metadata`。

### 6. tool_result

工具执行完成后的返回结果。

```json
{
  "type": "tool_result",
  "data": {
    "tool_name": "search_job_skills",
    "tool_call_id": "call_xxx",
    "output": {
      "results": [
        {
          "keyword": "Python",
          "items": [
            {
              "id": 66,
              "name": "Python",
              "description": "Python编程语言，用于AI开发、数据处理和Web应用开发"
            }
          ],
          "total": 1
        }
      ]
    },
    "metadata": {
      "langgraph_node": "tools",
      "langgraph_step": 3
    }
  }
}
```

前端建议：

- 不要把 `tool_result.output` 拼进 assistant 正文。
- 可以展示在工具调用记录面板中。
- 如果是开发调试模式，可以展开查看完整 JSON。
- 如果是普通用户聊天界面，可以只展示“工具调用完成”。

### 7. run_end

表示本次流式运行结束。

```json
{
  "type": "run_end",
  "data": {
    "run_id": "xxx",
    "thread_id": "TEST6",
    "elapsed_ms": 12345.67,
    "answer_length": 320
  }
}
```

前端建议：

- 关闭 loading 状态。
- 标记 assistant 消息完成。
- `answer_length` 可用于判断本次是否产生了正文。

### 8. error

运行失败。

```json
{
  "type": "error",
  "data": {
    "run_id": "xxx",
    "message": "模型服务出错：...",
    "error_type": "BadRequestError"
  }
}
```

前端建议：

- 关闭 loading。
- 展示错误提示。
- 可保留已收到的 `model_delta` 内容。

## 四、前端 TypeScript 类型建议

```ts
export type AgentStreamEventType =
  | 'run_start'
  | 'agent_assembled'
  | 'reasoning_delta'
  | 'model_delta'
  | 'tool_call'
  | 'tool_result'
  | 'run_end'
  | 'error'

export interface AgentStreamEvent<T = unknown> {
  type: AgentStreamEventType | string
  data: T
}

export interface RunStartData {
  run_id: string
  thread_id: string
  persistent_conversation: boolean
  stream: boolean
}

export interface ReasoningDeltaData {
  content: string
}

export interface ModelDeltaData {
  content: string
}

export interface ToolCallData {
  tool_name: string
  args: Record<string, unknown>
  id?: string | null
  metadata?: Record<string, unknown>
}

export interface ToolResultData {
  tool_name: string
  tool_call_id?: string | null
  output: unknown
  metadata?: Record<string, unknown>
}

export interface RunEndData {
  run_id: string
  thread_id: string
  elapsed_ms: number
  answer_length: number
}

export interface ErrorData {
  run_id?: string
  message: string
  error_type?: string
}
```

## 五、前端解析示例

```ts
function parseSseBlock(block: string) {
  let eventType = 'message'
  const dataLines: string[] = []

  for (const rawLine of block.split('
')) {
    const line = rawLine.replace(/$/, '')
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim() || 'message'
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  const data = dataLines.join('
')
  if (!data) return null

  const parsed = JSON.parse(data)
  return {
    ...parsed,
    type: parsed.type || eventType,
  }
}

export async function runAgentStream(payload: Record<string, unknown>, onEvent: (event: AgentStreamEvent) => void) {
  const response = await fetch('/api/agent/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...payload,
      stream: true,
    }),
  })

  if (!response.ok || !response.body) {
    throw new Error(`Agent stream failed: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const normalized = buffer.replace(/
/g, '
')
    const blocks = normalized.split('

')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      const event = parseSseBlock(block)
      if (event) onEvent(event)
    }
  }

  const tail = buffer.trim()
  if (tail) {
    const event = parseSseBlock(tail)
    if (event) onEvent(event)
  }
}
```

## 六、推荐渲染逻辑

```ts
let answer = ''
let reasoning = ''
const toolLogs: Array<AgentStreamEvent> = []

function handleAgentEvent(event: AgentStreamEvent) {
  switch (event.type) {
    case 'run_start':
      // 初始化运行状态。
      break

    case 'reasoning_delta':
      reasoning += (event.data as ReasoningDeltaData).content
      break

    case 'model_delta':
      answer += (event.data as ModelDeltaData).content
      break

    case 'tool_call':
    case 'tool_result':
      toolLogs.push(event)
      break

    case 'run_end':
      // 标记完成，answer 就是最终回复。
      break

    case 'error':
      // 展示错误提示。
      break
  }
}
```

## 七、注意事项

1. `model_delta` 才是 assistant 正文，前端最终回答只累计该事件。
2. `reasoning_delta` 是思考过程，不要拼进最终回答。
3. `tool_result` 是工具返回结果，不要拼进最终回答。
4. `tool_call` 和 `tool_result` 可以放入“执行过程”或“调试面板”。
5. 流式模式不返回统一 `Result` 包装，也不返回 `final` 事件。
6. 流式结束以 `run_end` 为准。
7. 如果后端返回 `error`，前端仍可以保留已经收到的正文和思考内容。
8. 如果使用 `agent_id`，前端尽量不要传空的 `system_prompt`、`tools`、`runtime_options`，让后端按模板运行。

## 八、页面展示建议

普通用户聊天页建议展示：

- assistant 正文：只展示 `model_delta` 累计结果。
- 思考过程：展示 `reasoning_delta`，默认可折叠。
- 执行过程：展示工具名称和状态，默认可折叠。

Agent 调试页建议展示：

- 所有事件列表。
- `tool_call.args`。
- `tool_result.output`。
- `agent_assembled` 中的模型、工具、中间件信息。
- `run_end.elapsed_ms` 和 `answer_length`。
