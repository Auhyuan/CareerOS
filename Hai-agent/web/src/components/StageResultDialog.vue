<script setup lang="ts">
import { computed } from 'vue'
import { Braces, FileText, X } from 'lucide-vue-next'

import type { WorkflowNode } from '../types'

const props = defineProps<{ node: WorkflowNode | null }>()
const emit = defineEmits<{ close: [] }>()

const resultEntries = computed(() => {
  if (!props.node) {
    return []
  }

  return Object.entries(props.node.result_data || {})
})

/** 将下划线字段名转换为更易读的展示名称。 */
function formatFieldName(fieldName: string): string {
  return fieldName
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

/** 判断字段值是否可以直接以文本形式展示。 */
function isScalar(value: unknown): boolean {
  return value === null || ['string', 'number', 'boolean'].includes(typeof value)
}

/** 将基础类型转换为界面文本。 */
function formatScalar(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '未填写'
  }

  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }

  return String(value)
}

/** 格式化时间，避免直接展示难读的 ISO 时间。 */
function formatTime(value: string | null): string {
  if (!value) {
    return '尚未完成'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>

<template>
  <div v-if="node" class="modal-backdrop" @mousedown.self="emit('close')">
    <section class="modal stage-result-modal" role="dialog" aria-modal="true" aria-label="查看阶段结果">
      <header>
        <div>
          <span class="modal-icon"><FileText :size="18" /></span>
          <div>
            <h2>{{ node.title }}结果</h2>
            <p>Agent 已保存的当前阶段最终结果</p>
          </div>
        </div>
        <button class="icon-button" type="button" title="关闭" @click="emit('close')">
          <X :size="18" />
        </button>
      </header>

      <div class="stage-result-meta">
        <span>版本 v{{ node.result_version }}</span>
        <span>{{ formatTime(node.completed_at) }}</span>
      </div>

      <section v-if="node.summary" class="stage-result-summary">
        <strong>阶段摘要</strong>
        <p>{{ node.summary }}</p>
      </section>

      <div v-if="resultEntries.length" class="stage-result-content">
        <section
          v-for="[fieldName, fieldValue] in resultEntries"
          :key="fieldName"
          class="stage-result-field"
        >
          <h3>{{ formatFieldName(fieldName) }}</h3>
          <p v-if="isScalar(fieldValue)" class="stage-result-value">
            {{ formatScalar(fieldValue) }}
          </p>
          <pre v-else>{{ JSON.stringify(fieldValue, null, 2) }}</pre>
        </section>
      </div>

      <div v-else class="stage-result-empty">
        <Braces :size="24" />
        <strong>暂无结构化结果</strong>
        <p>当前节点只有摘要，Agent 尚未保存详细阶段结果。</p>
      </div>

      <footer>
        <button class="primary" type="button" @click="emit('close')">关闭</button>
      </footer>
    </section>
  </div>
</template>
