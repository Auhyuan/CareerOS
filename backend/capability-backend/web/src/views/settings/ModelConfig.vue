/**
 * 9. 模型配置页（只读展示）
 */
<template>
  <div>
    <h2 class="page-title">⚙️ 模型配置</h2>

    <a-card v-if="config" :loading="loading">
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="Provider">{{ config.provider || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Base URL">{{ config.base_url || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Chat Model">{{ config.chat_model || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Embedding Model">{{ config.embedding_model || '-' }}</a-descriptions-item>
        <a-descriptions-item label="Rerank Model">{{ config.rerank_model || '-' }}</a-descriptions-item>
        <a-descriptions-item label="API Key 配置">
          <a-tag :color="config.has_api_key ? 'green' : 'red'">
            {{ config.has_api_key ? '✅ 已配置' : '❌ 未配置' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="LangSmith API Key">
          <a-tag :color="config.has_langsmith_api_key ? 'green' : 'default'">
            {{ config.has_langsmith_api_key ? '✅ 已配置' : '⛔ 未配置' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="LangSmith Tracing" :span="2">
          <a-tag :color="config.langsmith_tracing ? 'green' : 'default'">
            {{ config.langsmith_tracing ? '✅ 开启' : '⛔ 关闭' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="LangSmith Endpoint" :span="2">
          <code>{{ config.langsmith_endpoint || '-' }}</code>
        </a-descriptions-item>
        <a-descriptions-item label="LangSmith Project" :span="2">
          <code>{{ config.langsmith_project || '-' }}</code>
        </a-descriptions-item>
        <a-descriptions-item label="网关配置路径" :span="2">
          <code>{{ config.gateway_path || '-' }}</code>
        </a-descriptions-item>
        <a-descriptions-item label="可用模型别名" :span="2">
          <a-tag v-for="m in config.available_models || []" :key="m" color="blue" class="m-1">
            {{ m }}
          </a-tag>
          <span v-if="!(config.available_models || []).length">-</span>
        </a-descriptions-item>
      </a-descriptions>
    </a-card>
    <a-empty v-else-if="!loading" description="未加载到模型配置" />
  </div>
</template>

<script setup lang="ts">
/**
 * 模型配置页逻辑
 * - 只读展示后端 /agent/model/config 返回值
 */
import { onMounted, ref } from 'vue'
import { getModelConfig, type ModelConfigResponse } from '@/api/capabilities'

defineOptions({ name: 'ModelConfigView' })

const loading = ref(false)
const config = ref<ModelConfigResponse | null>(null)

async function load() {
  loading.value = true
  try {
    config.value = await getModelConfig()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-title {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
}
.m-1 {
  margin: 2px;
}
</style>
