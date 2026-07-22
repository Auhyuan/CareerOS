<!--
  知识库管理列表页
  - 卡片网格 + 状态筛选 + 关键字搜索
  - 接 /knowledge/bases/search
  - 操作：详情 / 文档 / 编辑 / 删除（后端尚未提供，前端展示 UI 占位 + disabled）
-->
<template>
  <div>
    <h2 class="page-title">📚 知识库管理</h2>

    <!-- 顶部筛选 -->
    <a-card class="mb-4">
      <div class="filter-bar">
        <div class="filter-left">
          <a-form layout="inline">
            <a-form-item label="关键字">
              <a-input
                v-model:value="filters.keyword"
                placeholder="搜索名称 / 描述"
                allow-clear
                style="width: 240px"
                @press-enter="onSearch"
              />
            </a-form-item>
            <a-form-item label="状态">
              <a-select
                v-model:value="filters.status"
                placeholder="全部"
                style="width: 140px"
                allow-clear
              >
                <a-select-option value="active">已启用</a-select-option>
                <a-select-option value="disabled">已停用</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item>
              <a-button type="primary" @click="onSearch">🔍 查询</a-button>
              <a-button class="ml-2" @click="onReset">重置</a-button>
            </a-form-item>
          </a-form>
        </div>
        <div class="filter-right">
          <a-button type="primary" @click="goCreate">➕ 新建知识库</a-button>
        </div>
      </div>
    </a-card>

    <!-- 加载态 -->
    <a-card v-if="loading">
      <a-skeleton active :paragraph="{ rows: 6 }" />
    </a-card>

    <!-- 错误态 -->
    <a-card v-else-if="error">
      <a-empty description="加载失败">
        <a-button type="primary" @click="loadList">重试</a-button>
        <div class="error-detail">{{ error }}</div>
      </a-empty>
    </a-card>

    <!-- 空状态 -->
    <a-card v-else-if="!list.length">
      <a-empty description="还没有任何知识库">
        <a-button type="primary" @click="goCreate">创建第一个知识库</a-button>
      </a-empty>
    </a-card>

    <!-- 卡片网格 -->
    <a-row v-else :gutter="[16, 16]">
      <a-col v-for="kb in list" :key="kb.knowledge_id" :xs="24" :sm="12" :md="12" :lg="8" :xl="8">
        <div class="kb-card">
          <!-- 头部：图标 + 名称 + 状态 -->
          <div class="kb-head">
            <div class="kb-icon">📘</div>
            <div class="kb-title-wrap">
              <div class="kb-title">
                {{ kb.name }}
                <a-tag :color="kb.status === 'active' ? 'green' : 'default'" style="margin-left: 4px">
                  {{ kb.status === 'active' ? '● 已启用' : '● 已停用' }}
                </a-tag>
              </div>
              <div v-if="kb.description" class="kb-desc">{{ kb.description }}</div>
            </div>
          </div>

          <!-- 元信息网格 -->
          <div class="kb-meta-grid">
            <div class="kb-meta-item">
              <span class="kb-label">集合</span>
              <code class="kb-code">{{ kb.collection_name }}</code>
            </div>
            <div class="kb-meta-item">
              <span class="kb-label">Embedding</span>
              <code class="kb-code">{{ kb.embedding_model_code }}</code>
            </div>
            <div class="kb-meta-item">
              <span class="kb-label">维度</span>
              <span class="kb-value">{{ kb.embedding_dimension }}</span>
            </div>
            <div class="kb-meta-item">
              <span class="kb-label">knowledge_id</span>
              <code class="kb-code kb-id">{{ kb.knowledge_id }}</code>
            </div>
          </div>

          <!-- 底部：时间 + 操作 -->
          <div class="kb-foot">
            <span class="kb-time">创建于 {{ formatDate(kb.created_at) }}</span>
            <span class="kb-actions">
              <a-tooltip title="后端尚未提供 get 接口">
                <a-button size="small" type="link" disabled>详情</a-button>
              </a-tooltip>
              <a-tooltip title="后端尚未提供 list_documents 接口">
                <a-button size="small" type="link" disabled>文档</a-button>
              </a-tooltip>
              <a-tooltip title="后端尚未提供 update 接口">
                <a-button size="small" type="link" disabled>编辑</a-button>
              </a-tooltip>
              <a-tooltip title="后端尚未提供 delete 接口">
                <a-button size="small" type="link" danger disabled>删除</a-button>
              </a-tooltip>
            </span>
          </div>
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
/**
 * 知识库管理列表
 * - 搜索 + 状态筛选
 * - 卡片网格展示
 * - 操作按钮占位（待后端补 API 后启用）
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchKnowledgeBases, type KnowledgeBaseItem } from '@/api/knowledge'

defineOptions({ name: 'KnowledgeList' })

const router = useRouter()

/* ===== 筛选条件 ===== */
const filters = reactive<{ keyword: string; status: string }>({
  keyword: '',
  status: '',
})

/* ===== 列表数据 ===== */
const list = ref<KnowledgeBaseItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

/* ===== 加载列表 ===== */
async function loadList() {
  loading.value = true
  error.value = null
  try {
    const params: { keyword?: string; status?: string } = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.status) params.status = filters.status
    list.value = await searchKnowledgeBases(params)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    list.value = []
  } finally {
    loading.value = false
  }
}

/* ===== 事件处理 ===== */
function onSearch() {
  loadList()
}

function onReset() {
  filters.keyword = ''
  filters.status = ''
  loadList()
}

function goCreate() {
  router.push('/knowledge/create')
}

/* ===== 工具函数 ===== */
function formatDate(iso: string | undefined | null): string {
  if (!iso) return '-'
  // 截取 yyyy-mm-dd，避免时区问题
  return iso.slice(0, 10)
}

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.page-title {
  margin: 0 0 16px 0;
  font-size: 20px;
  font-weight: 600;
}
.mb-4 {
  margin-bottom: 16px;
}
.ml-2 {
  margin-left: 8px;
}

/* 筛选条：左查询条件 + 右操作按钮 */
.filter-bar {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 16px;
  flex-wrap: wrap;
}
.filter-left {
  flex: 1;
  min-width: 0;
}
.filter-right {
  flex-shrink: 0;
  /* 双保险：即使父级 space-between 失效也能靠右 */
  margin-left: auto;
}

/* 错误信息 */
.error-detail {
  margin-top: 12px;
  color: #ff4d4f;
  font-size: 12px;
  max-width: 480px;
  word-break: break-all;
}

/* 卡片样式 */
.kb-card {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 18px 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.2s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.kb-card:hover {
  box-shadow: 0 4px 16px rgba(114, 46, 209, 0.08);
  border-color: #d3adf7;
  transform: translateY(-1px);
}

.kb-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.kb-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  background: linear-gradient(135deg, #f9f0ff 0%, #efdbff 100%);
}
.kb-title-wrap {
  flex: 1;
  min-width: 0;
}
.kb-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.kb-desc {
  margin-top: 4px;
  color: #595959;
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 12px;
}
.kb-meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.kb-label {
  color: #8c8c8c;
  flex-shrink: 0;
}
.kb-value {
  color: #1f1f1f;
  font-weight: 500;
}
.kb-code {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11px;
  color: #1f1f1f;
  background: rgba(114, 46, 209, 0.06);
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.kb-id {
  font-size: 10px;
  color: #8c8c8c;
}

.kb-foot {
  display: flex;
  align-items: center;
  padding-top: 10px;
  border-top: 1px dashed #f0f0f0;
  font-size: 12px;
  margin-top: auto;
}
.kb-time {
  color: #8c8c8c;
  flex: 1;
  min-width: 0;
}
.kb-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
</style>
