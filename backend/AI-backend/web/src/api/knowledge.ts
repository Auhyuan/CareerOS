/**
 * 知识库管理接口。
 * Agent 模板编辑页通过该接口选择允许检索的知识库。
 */
import { httpPost } from './http'

/** 知识库列表项。 */
export interface KnowledgeBaseItem {
  knowledge_id: string
  name: string
  description?: string | null
  collection_name: string
  embedding_model_code: string
  embedding_dimension: number
  split_config: Record<string, unknown>
  status: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** 创建知识库时明确绑定一个已启用的 Embedding 模型。 */
export interface KnowledgeBaseCreatePayload {
  name: string
  description?: string | null
  embedding_model_code: string
  split_config?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

/** 查询知识库列表。 */
export function searchKnowledgeBases(params: { keyword?: string; status?: string }) {
  return httpPost<KnowledgeBaseItem[]>('/knowledge/bases/search', params)
}

/** 创建并绑定 Embedding 模型的知识库。 */
export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return httpPost<KnowledgeBaseItem>('/knowledge/bases/create', payload)
}
