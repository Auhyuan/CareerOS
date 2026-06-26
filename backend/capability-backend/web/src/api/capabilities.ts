/**
 * 系统能力、健康检查与模型配置相关接口
 * 完全对齐后端 AgentCapabilityResponse / ModelConfigResponse / AgentHealth
 */
import { httpGet } from './http'

/** Agent 工具详情 */
export interface AgentToolInfo {
  name: string
  description: string
  group: string
  invokable: boolean
  invoke_note?: string | null
  args_schema: Record<string, any>
}

/** Agent 服务能力响应（/agent/capabilities） */
export interface AgentCapabilityResponse {
  service_name: string
  modules: string[]
  enabled_features: string[]
  /** 后端 list_tools() 返回的是字符串数组，不是对象 */
  registered_tools: string[]
  /** 后端返回的工具详情，包含参数 Schema 和动态工具说明 */
  tools?: AgentToolInfo[]
}

/** 获取 Agent 服务能力清单 */
export function getCapabilities() {
  return httpGet<AgentCapabilityResponse>('/agent/capabilities')
}

/** 模型配置响应（/agent/model/config） */
export interface ModelConfigResponse {
  gateway_path: string
  available_models: string[]
  provider: string
  base_url: string
  chat_model: string
  embedding_model?: string | null
  rerank_model?: string | null
  langsmith_tracing: boolean
  langsmith_endpoint: string
  langsmith_project: string
  has_api_key: boolean
  has_langsmith_api_key: boolean
}

/** 获取当前模型配置 */
export function getModelConfig() {
  return httpGet<ModelConfigResponse>('/agent/model/config')
}

/** Agent 健康检查（/agent/health） */
export interface AgentHealthResponse {
  service: string
  status: string
}

/** Agent 健康检查 */
export function getHealth() {
  return httpGet<AgentHealthResponse>('/agent/health')
}
