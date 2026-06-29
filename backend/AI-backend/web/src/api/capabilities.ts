/**
 * 绯荤粺鑳藉姏銆佸仴搴锋鏌ヤ笌妯″瀷閰嶇疆鐩稿叧鎺ュ彛
 * 瀹屽叏瀵归綈鍚庣 AgentCapabilityResponse / ModelConfigResponse / AgentHealth
 */
import { httpGet } from './http'

/** Agent 宸ュ叿璇︽儏 */
export interface AgentToolInfo {
  name: string
  description: string
  group: string
  invokable: boolean
  invoke_note?: string | null
  args_schema: Record<string, any>
}

/** Agent 鏈嶅姟鑳藉姏鍝嶅簲锛?agent/capabilities锛?*/
export interface AgentCapabilityResponse {
  service_name: string
  modules: string[]
  enabled_features: string[]
  /** 鍚庣 list_tools() 杩斿洖鐨勬槸瀛楃涓叉暟缁勶紝涓嶆槸瀵硅薄 */
  registered_tools: string[]
  /** 鍚庣杩斿洖鐨勫伐鍏疯鎯咃紝鍖呭惈鍙傛暟 Schema 鍜屽姩鎬佸伐鍏疯鏄?*/
  tools?: AgentToolInfo[]
}

/** 鑾峰彇 Agent 鏈嶅姟鑳藉姏娓呭崟 */
export function getCapabilities() {
  return httpGet<AgentCapabilityResponse>('/agent/capabilities')
}

/** 模型配置摘要响应（/agent/model/config） */
export interface ModelConfigResponse {
  available_models: string[]
  chat_models: string[]
  embedding_models: string[]
  rerank_models: string[]
  langsmith_tracing: boolean
  langsmith_endpoint: string
  langsmith_project: string
  has_langsmith_api_key: boolean
}

/** 获取当前模型配置摘要 */
export function getModelConfig() {
  return httpGet<ModelConfigResponse>('/agent/model/config')
}
/** Agent 鍋ュ悍妫€鏌ワ紙/agent/health锛?*/
export interface AgentHealthResponse {
  service: string
  status: string
}

/** Agent 鍋ュ悍妫€鏌?*/
export function getHealth() {
  return httpGet<AgentHealthResponse>('/agent/health')
}
