/**
 * Agent 妯℃澘鐩稿叧鎺ュ彛
 * 瀛楁涓庤矾寰勫畬鍏ㄥ榻愬悗绔?/agent/templates/*
 */
import { httpPost } from './http'
import type { PageRequest, PageResponse } from './types'

/** 妯″瀷杩愯鍙傛暟锛圡odelRuntimeOptions锛?*/
export interface ModelRuntimeOptions {
  model_code?: string | null
  temperature?: number
  max_tokens?: number
  timeout_seconds?: number
  max_retries?: number
}

/** 鍙€夎兘鍔涳紙AgentOptionalFeatures锛?*/
export interface AgentOptionalFeatures {
  long_term_memory_enabled?: boolean
}

/** Agent 妯℃澘杩愯閰嶇疆锛圓gentTemplateConfig锛?*/
export interface AgentTemplateConfig {
  system_prompt?: string | null
  tools?: string[]
  optional_features?: AgentOptionalFeatures
  is_sub_agent?: boolean
  a2a?: { sub_agent_list?: string[] } | null
  runtime_options?: ModelRuntimeOptions
  /** 妯℃澘 config 鏄?JSONB锛屽悗绔?ConfigDict(extra='allow') 鍏佽鍏朵粬鎵╁睍瀛楁 */
  [key: string]: unknown
}

/** Agent 妯℃澘瑙嗗浘锛圓gentTemplateView锛?*/
export interface AgentTemplate {
  agent_id: string
  agent_name: string
  description?: string | null
  config: AgentTemplateConfig
  status: string
  created_at?: string | null
  updated_at?: string | null
}

/** 鍒嗛〉鎼滅储妯℃澘 */
export function searchAgentTemplates(params: PageRequest & { keyword?: string; status?: string }) {
  return httpPost<PageResponse<AgentTemplate>>('/agent/templates/search', params)
}

/** 鏌ヨ妯℃澘璇︽儏 */
export function getAgentTemplateDetail(agent_id: string) {
  return httpPost<AgentTemplate>('/agent/templates/detail', { agent_id })
}

/** 鍒涘缓鎴栨洿鏂版ā鏉?*/
export function upsertAgentTemplate(payload: {
  agent_id: string
  agent_name: string
  description?: string | null
  config: AgentTemplateConfig
  status?: string
}) {
  return httpPost<AgentTemplate>('/agent/templates/upsert', payload)
}

/** 鎵归噺鍒犻櫎妯℃澘锛堜笌鍚庣 /agent/templates/delete 鎺ュ彛瀵归綈锛岃姹備綋鎼哄甫 ID 鍒楄〃锛?*/
export function deleteAgentTemplate(agent_ids: string[]) {
  return httpPost<number>('/agent/templates/delete', { agent_ids })
}

