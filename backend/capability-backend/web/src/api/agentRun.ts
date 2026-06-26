/**
 * Agent 运行相关接口
 * 字段与路径完全对齐后端 /agent/runs/* 与 /agent/run
 */
import { httpPost } from './http'
import type { PageRequest, PageResponse } from './types'

/** Agent 运行记录视图（AgentRunView） */
export interface AgentRun {
  run_id: string
  run_type: 'main' | 'sub' | string
  parent_run_id?: string | null
  agent_id?: string | null
  conversation_id?: string | null
  user_message_id?: string | null
  assistant_message_id?: string | null
  query?: string | null
  answer?: string | null
  status: 'running' | 'success' | 'failed' | string
  error_message?: string | null
  elapsed_ms?: number | null
  metadata?: Record<string, unknown>
  started_at?: string | null
  finished_at?: string | null
}

/** Agent 主子运行链路（AgentRunChainResponse） */
export interface AgentRunChain {
  run_id: string
  items: AgentRun[]
}

/** 搜索运行记录请求（AgentRunSearchRequest） */
export interface SearchAgentRunsParams extends PageRequest {
  run_id?: string
  run_type?: 'main' | 'sub'
  parent_run_id?: string
  agent_id?: string
  conversation_id?: string
  status?: 'running' | 'success' | 'failed'
}

/** 搜索运行记录 */
export function searchAgentRuns(params: SearchAgentRunsParams) {
  return httpPost<PageResponse<AgentRun>>('/agent/runs/search', params)
}

/** 查询单条运行详情 */
export function getAgentRunDetail(run_id: string) {
  return httpPost<AgentRun>('/agent/runs/detail', { run_id })
}

/** 查询主子运行链路 */
export function getAgentRunChain(run_id: string) {
  return httpPost<AgentRunChain>('/agent/runs/chain', { run_id })
}

/** Agent 运行请求（AgentRunRequest） */
export interface AgentRunRequestPayload {
  query: string
  conversation_id?: string
  stream?: boolean
  system_prompt?: string
  response_format?: Record<string, unknown>
  inputs?: Record<string, unknown>
  files?: Array<Record<string, unknown>>
  tools?: string[]
  optional_features?: {
    long_term_memory_enabled?: boolean
    a2a_enabled?: boolean
    knowledge_retrieval_enabled?: boolean
    tool_logging_enabled?: boolean
  }
  a2a?: Record<string, unknown>
  runtime_options?: {
    model?: string | null
    temperature?: number
    max_tokens?: number
    timeout_seconds?: number
    max_retries?: number
    stateless?: boolean
  }
}

/** Agent 运行响应（AgentRunResponse） */
export interface AgentRunResponse {
  run_id: string
  answer: string
  structured_output?: Record<string, unknown> | null
}

/** 同步运行 Agent（stream=false） */
export function runAgent(payload: AgentRunRequestPayload) {
  return httpPost<AgentRunResponse>('/agent/run', { ...payload, stream: false })
}

/** SSE 事件类型 */
export interface AgentStreamEvent {
  type: string
  content?: string
  answer?: string
  run_id?: string
  message_id?: string
  delta?: string
  [key: string]: unknown
}

/**
 * 流式运行 Agent（SSE）
 * 后端返回 text/event-stream 格式，event 行 + data 行
 * 事件类型：message / start / end / error 等
 */
export async function runAgentStream(
  payload: AgentRunRequestPayload,
  onEvent: (event: AgentStreamEvent) => void,
  onError?: (err: Error) => void,
  onDone?: () => void,
) {
  const baseURL = (import.meta.env.VITE_API_BASE as string) || '/api'
  try {
    const response = await fetch(`${baseURL}/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, stream: true }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    // 持续读取 SSE 流，按 event/data 解析
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      let currentEvent = 'message'
      for (const raw of lines) {
        const line = raw.replace(/\r$/, '')
        if (!line) {
          currentEvent = 'message'
          continue
        }
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim() || 'message'
        } else if (line.startsWith('data:')) {
          const data = line.slice(5).trim()
          if (!data) continue
          try {
            const json = JSON.parse(data)
            onEvent({ ...(json as object), type: (json as AgentStreamEvent).type || currentEvent })
          } catch {
            onEvent({ type: currentEvent, content: data })
          }
        }
      }
    }
    onDone?.()
  } catch (err) {
    onError?.(err as Error)
  }
}
