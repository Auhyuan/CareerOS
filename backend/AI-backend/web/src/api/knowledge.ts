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
  embedding_model: string
  embedding_dimension: number
  split_config: Record<string, unknown>
  status: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** 查询知识库列表。 */
export function searchKnowledgeBases(params: { keyword?: string; status?: string }) {
  return httpPost<KnowledgeBaseItem[]>('/knowledge/bases/search', params)
}
