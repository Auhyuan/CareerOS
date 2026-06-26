<!--
  工具管理页
  - 展示常规工具和动态工具详情
  - 根据工具 args_schema 自动渲染调试表单
  - 调试调用 POST /agent/tools/invoke，只允许调用 invokable=true 的常规工具
-->
<template>
  <div>
    <h2 class="page-title">工具管理</h2>

    <a-row :gutter="16">
      <!-- 左侧：工具列表 -->
      <a-col :span="9">
        <a-card title="工具列表" :loading="loading">
          <a-empty v-if="!tools.length" description="暂无工具" />
          <a-list v-else :data-source="tools" :pagination="{ pageSize: 10 }">
            <template #renderItem="{ item }">
              <a-list-item
                :class="['tool-item', { active: selectedTool?.name === item.name }]"
                @click="selectTool(item)"
              >
                <a-list-item-meta>
                  <template #title>
                    <a-space>
                      <span>{{ item.name }}</span>
                      <a-tag :color="item.group === 'a2a' ? 'cyan' : 'blue'">{{ item.group }}</a-tag>
                      <a-tag v-if="!item.invokable" color="orange">动态</a-tag>
                    </a-space>
                  </template>
                  <template #description>
                    <div class="tool-desc">{{ shortDescription(item.description) }}</div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>

      <!-- 右侧：工具详情和调试区 -->
      <a-col :span="15">
        <a-card :title="selectedTool ? `工具详情 - ${selectedTool.name}` : '工具详情'">
          <a-empty v-if="!selectedTool" description="请先选择左侧工具" />
          <div v-else>
            <a-descriptions :column="1" size="small" bordered class="mb-4">
              <a-descriptions-item label="名称">{{ selectedTool.name }}</a-descriptions-item>
              <a-descriptions-item label="分组">
                <a-tag :color="selectedTool.group === 'a2a' ? 'cyan' : 'blue'">{{ selectedTool.group }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="可直接调试">
                <a-tag :color="selectedTool.invokable ? 'green' : 'orange'">
                  {{ selectedTool.invokable ? '是' : '否' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item v-if="selectedTool.invoke_note" label="调用说明">
                {{ selectedTool.invoke_note }}
              </a-descriptions-item>
              <a-descriptions-item label="说明">
                <pre class="description-box">{{ selectedTool.description || '暂无说明' }}</pre>
              </a-descriptions-item>
            </a-descriptions>

            <a-tabs>
              <a-tab-pane key="form" tab="参数表单">
                <a-alert
                  v-if="!selectedTool.invokable"
                  type="warning"
                  show-icon
                  class="mb-4"
                  :message="selectedTool.invoke_note || '该工具不能脱离 Agent 运行上下文直接调用'"
                />

                <a-form layout="vertical">
                  <template v-if="schemaFields.length">
                    <a-form-item
                      v-for="field in schemaFields"
                      :key="field.name"
                      :label="fieldLabel(field)"
                      :extra="field.description"
                    >
                      <a-input-number
                        v-if="field.type === 'integer' || field.type === 'number'"
                        v-model:value="formValues[field.name]"
                        :min="field.minimum"
                        :max="field.maximum"
                        style="width: 100%"
                      />
                      <a-switch
                        v-else-if="field.type === 'boolean'"
                        v-model:checked="formValues[field.name]"
                      />
                      <a-textarea
                        v-else-if="isLongTextField(field)"
                        v-model:value="formValues[field.name]"
                        :rows="4"
                        :maxlength="field.maxLength"
                        show-count
                      />
                      <a-input
                        v-else
                        v-model:value="formValues[field.name]"
                        :maxlength="field.maxLength"
                        allow-clear
                      />
                    </a-form-item>
                  </template>
                  <a-empty v-else description="该工具未声明参数" />

                  <a-space>
                    <a-button type="primary" :loading="running" :disabled="!selectedTool.invokable" @click="onRun">
                      调用工具
                    </a-button>
                    <a-button @click="resetForm">重置参数</a-button>
                  </a-space>
                </a-form>
              </a-tab-pane>

              <a-tab-pane key="schema" tab="参数 Schema">
                <pre class="result-box light">{{ prettyJson(selectedTool.args_schema || {}) }}</pre>
              </a-tab-pane>
            </a-tabs>

            <a-divider>调用结果</a-divider>
            <a-spin :spinning="running">
              <pre v-if="result" class="result-box">{{ result }}</pre>
              <a-empty v-else description="尚无结果" />
            </a-spin>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
/**
 * 工具管理页逻辑。
 * - 从 /agent/capabilities 读取工具详情。
 * - 根据 args_schema.properties 自动生成调试表单。
 * - 通过 /agent/tools/invoke 调试调用常规工具。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { getCapabilities, type AgentToolInfo } from '@/api/capabilities'
import { invokeAgentTool } from '@/api/tools'

defineOptions({ name: 'ToolManagerView' })

interface ToolSchemaField {
  name: string
  type?: string
  title?: string
  description?: string
  default?: unknown
  minimum?: number
  maximum?: number
  minLength?: number
  maxLength?: number
  required: boolean
}

const loading = ref(false)
const tools = ref<AgentToolInfo[]>([])
const selectedTool = ref<AgentToolInfo | null>(null)
const running = ref(false)
const result = ref('')
const formValues = reactive<Record<string, any>>({})

/** 当前选中工具的参数字段列表。 */
const schemaFields = computed<ToolSchemaField[]>(() => {
  const schema = selectedTool.value?.args_schema || {}
  const properties = schema.properties || {}
  const required = new Set<string>(schema.required || [])
  return Object.entries(properties).map(([name, raw]) => {
    const item = raw as Record<string, any>
    return {
      name,
      type: item.type,
      title: item.title,
      description: item.description,
      default: item.default,
      minimum: item.minimum,
      maximum: item.maximum,
      minLength: item.minLength,
      maxLength: item.maxLength,
      required: required.has(name),
    }
  })
})

/** 加载工具详情列表。 */
async function load() {
  loading.value = true
  try {
    const cap = await getCapabilities()
    tools.value = cap.tools?.length
      ? cap.tools
      : (cap.registered_tools || []).map((name) => ({
          name,
          description: '',
          group: 'regular',
          invokable: true,
          invoke_note: null,
          args_schema: {},
        }))
    if (!selectedTool.value && tools.value.length) selectTool(tools.value[0])
  } finally {
    loading.value = false
  }
}

/** 选择工具并根据 schema 初始化表单。 */
function selectTool(tool: AgentToolInfo) {
  selectedTool.value = tool
  result.value = ''
  resetForm()
}

/** 根据 schema 默认值重置表单。 */
function resetForm() {
  Object.keys(formValues).forEach((key) => delete formValues[key])
  schemaFields.value.forEach((field) => {
    if (field.default !== undefined) {
      formValues[field.name] = field.default
    } else if (field.type === 'integer' || field.type === 'number') {
      formValues[field.name] = undefined
    } else if (field.type === 'boolean') {
      formValues[field.name] = false
    } else {
      formValues[field.name] = ''
    }
  })
  result.value = ''
}

/** 调试调用工具。 */
async function onRun() {
  if (!selectedTool.value) return
  const missingField = schemaFields.value.find((field) => field.required && isEmptyValue(formValues[field.name]))
  if (missingField) {
    message.error(`请填写必填参数：${missingField.name}`)
    return
  }

  running.value = true
  result.value = ''
  try {
    const args = buildArgs()
    const res = await invokeAgentTool({ tool_name: selectedTool.value.name, args })
    result.value = prettyJson(res)
  } catch (e: any) {
    result.value = `调用失败：${e?.message || e}`
  } finally {
    running.value = false
  }
}

/** 构建工具调用参数，过滤空的非必填字段。 */
function buildArgs() {
  const args: Record<string, unknown> = {}
  schemaFields.value.forEach((field) => {
    const value = formValues[field.name]
    if (!field.required && isEmptyValue(value)) return
    args[field.name] = value
  })
  return args
}

/** 判断字段是否为空。 */
function isEmptyValue(value: unknown) {
  return value === undefined || value === null || value === ''
}

/** 生成字段展示标题。 */
function fieldLabel(field: ToolSchemaField) {
  return `${field.name}${field.required ? ' *' : ''}`
}

/** 判断是否应该使用多行文本。 */
function isLongTextField(field: ToolSchemaField) {
  return (field.maxLength || 0) > 500 || field.name.toLowerCase().includes('description') || field.name.toLowerCase().includes('query')
}

/** 格式化 JSON。 */
function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

/** 截断列表描述。 */
function shortDescription(value: string) {
  const firstLine = (value || '暂无说明').trim().split('\n')[0]
  return firstLine.length > 80 ? `${firstLine.slice(0, 80)}...` : firstLine
}

onMounted(load)
</script>

<style scoped>
.page-title {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
}
.tool-item {
  cursor: pointer;
  transition: background 0.2s;
}
.tool-item:hover {
  background: #f5f5f5;
}
.tool-item.active {
  background: #e6f4ff;
}
.tool-desc {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}
.description-box {
  max-height: 160px;
  margin: 0;
  white-space: pre-wrap;
  color: #374151;
  font-size: 12px;
}
.result-box {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  max-height: 420px;
  overflow: auto;
  font-size: 12px;
  margin: 0;
}
.result-box.light {
  background: #f8fafc;
  color: #111827;
  border: 1px solid #e5e7eb;
}
.mb-4 {
  margin-bottom: 16px;
}
</style>
