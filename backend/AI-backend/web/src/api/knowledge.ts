/**
 * 知识库管理接口。
 * Agent 模板编辑页通过该接口选择允许检索的知识库。
 */
import { httpGet, httpPost } from './http'

/* ============================================================
 * 知识库基础 CRUD
 * ============================================================ */

/** 知识库列表项（与后端 KnowledgeBaseResponse 对齐）。 */
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
export function searchKnowledgeBases(params: { keyword?: string; status?: string } = {}) {
  return httpPost<KnowledgeBaseItem[]>('/knowledge/bases/search', params)
}

/** 创建并绑定 Embedding 模型的知识库。 */
export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return httpPost<KnowledgeBaseItem>('/knowledge/bases/create', payload)
}

/* ============================================================
 * 文档入库（提交 → 状态查询 → 重试）
 * ============================================================ */

/** 单一文档切片方式配置。 */
export interface KnowledgeSplitMethodConfig {
  type: 'markdown' | 'markdown_header' | 'recursive_character' | 'character' | 'qa_separator'
  chunk_size?: number
  chunk_overlap?: number
  separator?: string
  headers?: string[]
}

/** Markdown 标题切块后递归细切策略。 */
export interface KnowledgeSplitStrategyConfig {
  type: 'markdown_document_header_then_recursive'
  chunk_size?: number
  chunk_overlap?: number
  headers?: string[]
}

/** 提交入库请求：把已上传的文件 ID 关联到知识库。 */
export interface KnowledgeDocumentSubmitPayload {
  knowledge_id: string
  file_id: string
  force_reindex?: boolean
  priority?: number
  split_method?: KnowledgeSplitMethodConfig
  split_strategy?: KnowledgeSplitStrategyConfig
}

/** 文档关系记录。 */
export interface KnowledgeDocumentRecord {
  id: number
  knowledge_id: string
  file_id: string
  status: string
  index_version: number
  chunk_count: number
  error_message?: string | null
  indexed_at?: string | null
  created_at: string
  updated_at: string
}

/** 入库任务状态。 */
export interface IngestionRunRecord {
  run_id: string
  document_id: number
  knowledge_id: string
  file_id: string
  operation: string
  status: string
  priority: number
  worker_id?: string | null
  retry_count: number
  max_retries: number
  error_message?: string | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
}

/** 提交入库任务的响应（包含文档关系和入库任务）。 */
export interface KnowledgeDocumentSubmitResponse {
  document: KnowledgeDocumentRecord
  run: IngestionRunRecord | null
  reused_active_run: boolean
}

/** 提交文件入库到指定知识库。 */
export function submitKnowledgeDocument(payload: KnowledgeDocumentSubmitPayload) {
  return httpPost<KnowledgeDocumentSubmitResponse>('/knowledge/documents/submit', payload)
}

/** 查询入库任务状态。 */
export function getIngestionRunStatus(runId: string) {
  return httpPost<IngestionRunRecord>('/knowledge/ingestion/status', { run_id: runId })
}

/** 重新提交失败的入库任务。 */
export function retryIngestionRun(runId: string) {
  return httpPost<IngestionRunRecord>('/knowledge/ingestion/retry', { run_id: runId })
}

/* ============================================================
 * 调试 / 高级能力
 * ============================================================ */

/** 切片预览输入。 */
export interface SplitPreviewInput {
  text: string
  chunk_size: number
  chunk_overlap: number
  separator?: string
}

/** 切片结果片段。 */
export interface SplitPreviewChunk {
  index: number
  text: string
  token_count?: number
}

/** 切片预览输出。 */
export interface SplitPreviewOutput {
  chunks: SplitPreviewChunk[]
  total_chunks: number
}

/** 预览文本切片效果（不写入知识库）。 */
export function previewSplit(payload: SplitPreviewInput) {
  return httpPost<SplitPreviewOutput>('/knowledge/split/preview', payload)
}

/** 预览 Embedding 向量（不写入 Milvus）。 */
export function previewEmbedding(modelCode: string, text: string) {
  return httpPost<{ model_code: string; dimension: number; embedding: number[] }>(
    '/knowledge/embedding/preview',
    { model_code: modelCode, text },
  )
}

/** 服务存活检查。 */
export function checkKnowledgeHealth() {
  return httpGet<{ service: string; status: string }>('/knowledge/health')
}
