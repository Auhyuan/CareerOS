/**
 * 模型配置接口
 * 对齐后端 /agent/models/*，用于管理平台模型资源池。
 */
import { httpPost } from './http'
import type { PageResponse } from './types'

export type ModelType = 'chat' | 'embedding' | 'rerank'

/** 模型配置视图，本地部署场景下 api_key 作为普通配置返回。 */
export interface ModelConfigItem {
  id?: number | null
  model_code: string
  model_name: string
  model_type: ModelType
  base_url: string
  api_key?: string | null
  api_type: string
  support_stream: boolean
  support_tool_calling: boolean
  support_structured_output: boolean
  is_multimodal: boolean
  enabled: boolean
  extra_config?: Record<string, unknown> | null
  description?: string | null
  created_at?: string | null
  updated_at?: string | null
}

/** 新增或更新模型配置请求。 */
export interface ModelConfigUpsertPayload {
  original_model_code?: string | null
  model_code: string
  model_name: string
  model_type: ModelType
  base_url: string
  api_key?: string | null
  api_type?: string
  support_stream?: boolean
  support_tool_calling?: boolean
  support_structured_output?: boolean
  is_multimodal?: boolean
  enabled?: boolean
  extra_config?: Record<string, unknown> | null
  description?: string | null
}

/** 查询模型配置列表。 */
export function searchModelConfigs(params: {
  keyword?: string | null
  model_type?: ModelType | null
  enabled?: boolean | null
  page?: number
  page_size?: number
}) {
  return httpPost<PageResponse<ModelConfigItem>>('/agent/models/search', params)
}

/** 查询模型配置详情。 */
export function getModelConfigDetail(model_code: string) {
  return httpPost<ModelConfigItem | null>('/agent/models/detail', { model_code })
}

/** 新增或更新模型配置。 */
export function upsertModelConfig(payload: ModelConfigUpsertPayload) {
  return httpPost<ModelConfigItem>('/agent/models/upsert', payload)
}

/** 批量删除模型配置。 */
export function deleteModelConfigs(model_codes: string[]) {
  return httpPost<number>('/agent/models/delete', { model_codes })
}
