<!--
  知识库新建表单
  - 3 步表单：基础信息 / Embedding 模型（从 model_configs 拉取）/ 检索与分块
  - 提交：POST /knowledge/bases/create
  - 注意：当前只支持 create 模式；编辑模式后端尚未提供 update API
-->
<template>
  <div>
    <!-- 顶部操作条 -->
    <div class="page-header">
      <a-button type="link" @click="goBack">← 返回列表</a-button>
      <h2 class="page-title">📚 新建知识库</h2>
    </div>

    <!-- 架构升级提示 -->
    <a-alert
      class="mb-4"
      type="info"
      show-icon
      message="v2：Embedding 由平台 ModelConfig 统一管理"
      description="创建知识库时通过 embedding_model_code 引用平台已配置的 Embedding 模型。向量维度、API 连接信息由平台自动读取，创建后不可更改。"
    />

    <!-- ===== 1. 基础信息 ===== -->
    <a-card class="form-card" title="① 基础信息">
      <p class="form-desc">知识库的名称和用途说明，便于 Agent 模板引用时识别。</p>
      <a-form
        ref="basicFormRef"
        :model="form"
        :rules="basicRules"
        layout="vertical"
      >
        <a-form-item label="知识库名称" required>
          <a-input
            v-model:value="form.name"
            placeholder="如：通用技能库"
            show-count
            :maxlength="50"
            allow-clear
          />
          <div class="form-help">建议使用业务可读的名称，例如「互联网产品面试题库」</div>
        </a-form-item>

        <a-form-item label="描述">
          <a-textarea
            v-model:value="form.description"
            placeholder="说明这个知识库涵盖的内容范围、典型使用场景"
            :maxlength="200"
            show-count
            :rows="3"
            allow-clear
          />
        </a-form-item>

        <a-form-item label="集合名称 (Collection)" required>
          <a-input
            v-model:value="form.collection_name"
            placeholder="留空将根据名称 + 模型自动生成"
            allow-clear
          />
          <div class="form-help">
            Milvus 中的 Collection 名称，<b>命名后不可修改</b>。
          </div>
          <a-alert
            v-if="!form.collection_name && form.name"
            type="info"
            show-icon
            style="margin-top: 8px"
          >
            <template #message>
              自动生成预览：<code>kb_{{ slugify(form.name) }}_{{ form.embedding_model_code || 'model' }}</code>
            </template>
          </a-alert>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- ===== 2. Embedding 模型 ===== -->
    <a-card class="form-card" title="② Embedding 模型">
      <p class="form-desc">
        从平台 <code>model_configs</code> 拉取已启用的 Embedding 模型。选定后该知识库所有文档将以该模型向量化存储。
      </p>
      <a-alert
        class="mb-4"
        type="info"
        show-icon
        message="数据来源：模型配置 / model_configs（仅展示 type=embedding 且已启用）"
      >
        <template #action>
          <a-button size="small" type="link" @click="goModelConfig">前往配置 →</a-button>
        </template>
      </a-alert>

      <!-- 加载态 -->
      <a-skeleton v-if="loadingModels" active :paragraph="{ rows: 3 }" />

      <!-- 空状态：平台没配置任何 embedding 模型 -->
      <a-empty
        v-else-if="!embeddingModels.length"
        description="平台尚未配置任何已启用的 Embedding 模型"
      >
        <a-button type="primary" @click="goModelConfig">前往模型配置</a-button>
      </a-empty>

      <!-- 模型列表 -->
      <a-radio-group
        v-else
        v-model:value="form.embedding_model_code"
        style="width: 100%"
      >
        <div class="model-list">
          <div
            v-for="m in embeddingModels"
            :key="m.model_code"
            class="model-row"
            :class="{ selected: form.embedding_model_code === m.model_code }"
            @click="form.embedding_model_code = m.model_code"
          >
            <a-radio :value="m.model_code" />
            <div class="model-row-body">
              <div class="model-row-head">
                <code class="model-row-code">{{ m.model_code }}</code>
                <a-tag v-if="m.model_code === 'emb-text-v3'" color="green">推荐</a-tag>
                <a-tag v-if="isSelfHosted(m.base_url)" color="orange">自部署</a-tag>
                <a-tag color="green">● 已启用</a-tag>
              </div>
              <div class="model-row-name">
                {{ m.description || m.model_name }}
              </div>
              <div class="model-row-meta">
                <span>模型名 <b>{{ m.model_name }}</b></span>
                <span>·  base_url <b>{{ shortBaseUrl(m.base_url) }}</b></span>
                <span v-if="getDimension(m) !== null">
                  ·  维度 <b>{{ getDimension(m) }}</b>
                </span>
              </div>
            </div>
          </div>
        </div>
      </a-radio-group>
    </a-card>

    <!-- ===== 3. 检索与分块 ===== -->
    <a-card class="form-card" title="③ 检索与分块">
      <p class="form-desc">文档如何被切分与检索。如不确定，建议使用默认值。</p>
      <a-form :model="form.split_config" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="分块大小 (Chunk Size)">
              <a-input-number
                v-model:value="form.split_config.chunk_size"
                :min="100"
                :max="2000"
                :step="50"
                style="width: 100%"
              />
              <div class="form-help">tokens。文本内容推荐 300-800。</div>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="分块重叠 (Overlap)">
              <a-input-number
                v-model:value="form.split_config.chunk_overlap"
                :min="0"
                :max="500"
                :step="10"
                style="width: 100%"
              />
              <div class="form-help">tokens。推荐 chunk_size 的 10-20%。</div>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="分隔符">
          <a-select v-model:value="form.split_config.separator">
            <a-select-option value="\n\n">双换行（段落分隔，推荐）</a-select-option>
            <a-select-option value="\n">单换行</a-select-option>
            <a-select-option value="。\n">句号 + 换行</a-select-option>
            <a-select-option value="custom">自定义正则（暂不支持）</a-select-option>
          </a-select>
          <div class="form-help">用于把长文档切分为多个片段的边界标记。</div>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- ===== 提交区 ===== -->
    <div class="submit-bar">
      <a-button @click="goBack">取消</a-button>
      <a-button :loading="submitting" @click="onSubmit('draft')">保存为草稿</a-button>
      <a-button type="primary" :loading="submitting" @click="onSubmit('create')">
        创建
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 知识库新建表单
 * - 三步表单：基础信息 / Embedding 模型（来自 model_configs）/ 检索与分块
 * - 提交：POST /knowledge/bases/create
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { createKnowledgeBase } from '@/api/knowledge'
import { listEnabledEmbeddingModels, type ModelConfigItem } from '@/api/modelConfigs'

defineOptions({ name: 'KnowledgeForm' })

const router = useRouter()

/* ===== 平台 Embedding 模型 ===== */
const embeddingModels = ref<ModelConfigItem[]>([])
const loadingModels = ref(false)

async function loadEmbeddingModels() {
  loadingModels.value = true
  try {
    embeddingModels.value = await listEnabledEmbeddingModels()
  } catch (e) {
    message.error('加载 Embedding 模型失败：' + (e instanceof Error ? e.message : String(e)))
    embeddingModels.value = []
  } finally {
    loadingModels.value = false
  }
}

/* ===== 表单数据 ===== */
const form = reactive({
  name: '',
  description: '',
  collection_name: '',
  embedding_model_code: '',
  split_config: {
    chunk_size: 500,
    chunk_overlap: 50,
    separator: '\n\n',
  },
})

/* ===== 表单校验 ===== */
const basicRules = {
  name: [
    { required: true, message: '请输入知识库名称' },
    { min: 2, max: 50, message: '名称长度需在 2-50 字符' },
  ],
}

/* ===== 提交 ===== */
const submitting = ref(false)

async function onSubmit(mode: 'create' | 'draft') {
  if (!form.name) {
    message.warning('请输入知识库名称')
    return
  }
  if (!form.embedding_model_code) {
    message.warning('请选择一个 Embedding 模型')
    return
  }

  submitting.value = true
  try {
    // 集合名留空时按规则自动生成
    const finalCollectionName =
      form.collection_name || `kb_${slugify(form.name)}_${form.embedding_model_code}`

    const payload = {
      name: form.name,
      description: form.description || null,
      embedding_model_code: form.embedding_model_code,
      collection_name: finalCollectionName,
      split_config: form.split_config,
      metadata: { draft: mode === 'draft' },
    }
    const created = await createKnowledgeBase(payload)
    message.success(`知识库「${created.name}」创建成功`)
    router.push('/knowledge')
  } catch (e) {
    message.error('创建失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    submitting.value = false
  }
}

/* ===== 导航 ===== */
function goBack() {
  router.push('/knowledge')
}
function goModelConfig() {
  router.push('/settings/model')
}

/* ===== 工具函数 ===== */
/** 把名称转成 slug（用于自动生成 collection_name）。 */
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 30) || 'kb'
}

/** 从 extra_config 中读 dimension 字段。 */
function getDimension(model: ModelConfigItem): number | null {
  const dim = model.extra_config?.dimension
  return typeof dim === 'number' ? dim : null
}

/** 截短 base_url 显示。 */
function shortBaseUrl(url: string): string {
  try {
    const u = new URL(url)
    return u.host
  } catch {
    return url.length > 40 ? url.slice(0, 40) + '...' : url
  }
}

/** 判断是否为本地自部署。 */
function isSelfHosted(url: string): boolean {
  return /localhost|127\.0\.0\.1|10\.|192\.168\./.test(url)
}

onMounted(() => {
  loadEmbeddingModels()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.mb-4 {
  margin-bottom: 16px;
}
.form-card {
  margin-bottom: 16px;
}
.form-desc {
  color: #8c8c8c;
  font-size: 13px;
  margin: 0 0 16px 0;
  line-height: 1.5;
}
.form-help {
  color: #8c8c8c;
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.5;
}
.form-help code {
  font-family: 'SFMono-Regular', Consolas, monospace;
  background: #f5f5f5;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 11px;
}

/* Embedding 模型行 */
.model-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.model-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s;
}
.model-row:hover {
  border-color: #d3adf7;
  box-shadow: 0 2px 8px rgba(114, 46, 209, 0.06);
}
.model-row.selected {
  border-color: #722ed1;
  background: #f9f0ff;
  box-shadow: 0 0 0 1px #722ed1;
}
.model-row-body { flex: 1; min-width: 0; }
.model-row-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.model-row-code {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  font-weight: 600;
  color: #1f1f1f;
}
.model-row-name {
  color: #595959;
  font-size: 12px;
  margin-bottom: 4px;
}
.model-row-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #8c8c8c;
  flex-wrap: wrap;
}
.model-row-meta b {
  color: #1f1f1f;
  font-weight: 500;
  font-family: 'SFMono-Regular', Consolas, monospace;
}

/* 提交区 */
.submit-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  position: sticky;
  bottom: 16px;
  z-index: 10;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
}
</style>
