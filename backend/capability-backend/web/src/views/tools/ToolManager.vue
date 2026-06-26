<!--
  工具管理页
  - 展示已注册工具（后端 list_tools 返回字符串数组）
  - 工具调试：手动构造 JSON 参数，POST 到 /agent/tools/invoke
-->
<template>
  <div>
    <h2 class="page-title">🔧 工具管理</h2>

    <a-row :gutter="16">
      <!-- 左侧：工具列表 -->
      <a-col :span="10">
        <a-card title="已注册工具" :loading="loading">
          <a-empty v-if="!tools.length" description="暂无工具" />
          <a-list
            v-else
            :data-source="tools"
            :pagination="{ pageSize: 10 }"
          >
            <template #renderItem="{ item }">
              <a-list-item
                :class="['tool-item', { active: selectedTool === item }]"
                @click="selectTool(item)"
              >
                <a-list-item-meta :title="item">
                  <template #description>
                    <div class="text-gray-500 text-xs">已注册到 Agent 服务</div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>

      <!-- 右侧：调试区 -->
      <a-col :span="14">
        <a-card :title="`🧪 工具调试${selectedTool ? ' - ' + selectedTool : ''}`">
          <a-empty v-if="!selectedTool" description="请先选择左侧工具" />
          <div v-else>
            <a-descriptions :column="1" size="small" bordered class="mb-4">
              <a-descriptions-item label="名称">{{ selectedTool }}</a-descriptions-item>
            </a-descriptions>

            <a-form layout="vertical">
              <a-form-item label="参数 (JSON)">
                <a-textarea
                  v-model:value="paramsText"
                  :rows="8"
                  placeholder='{ "arg1": "value1" }'
                />
              </a-form-item>
              <a-space>
                <a-button type="primary" :loading="running" @click="onRun">▶ 调用</a-button>
                <a-button @click="onReset">重置</a-button>
              </a-space>
            </a-form>

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
 * 工具管理页逻辑
 * - 加载 /agent/capabilities 的 registered_tools（字符串数组）
 * - 工具调试：手动构造 JSON 参数，调用（后端若未提供 /agent/tools/invoke 则以提示信息代替）
 */
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { httpPost } from '@/api/http'
import { getCapabilities } from '@/api/capabilities'

defineOptions({ name: 'ToolManagerView' })

const loading = ref(false)
const tools = ref<string[]>([])
const selectedTool = ref<string | null>(null)
const paramsText = ref('{}')
const running = ref(false)
const result = ref('')

/** 加载工具列表 */
async function load() {
  loading.value = true
  try {
    const cap = await getCapabilities()
    tools.value = cap.registered_tools || []
  } finally {
    loading.value = false
  }
}

/** 选择工具 */
function selectTool(name: string) {
  selectedTool.value = name
  paramsText.value = '{}'
  result.value = ''
}

/** 调用工具 */
async function onRun() {
  let params: Record<string, unknown> = {}
  try {
    params = paramsText.value ? JSON.parse(paramsText.value) : {}
  } catch {
    message.error('参数 JSON 格式错误')
    return
  }
  running.value = true
  result.value = ''
  try {
    // 后端若无通用工具调试接口，则提示
    const res = await httpPost('/agent/tools/invoke', {
      tool_name: selectedTool.value,
      args: params,
    })
    result.value = JSON.stringify(res, null, 2)
  } catch (e: any) {
    result.value = `❌ 调用失败：${e?.message || e}\n\n(注：后端需提供 /agent/tools/invoke 调试接口)`
  } finally {
    running.value = false
  }
}

/** 重置 */
function onReset() {
  paramsText.value = '{}'
  result.value = ''
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
.result-box {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  max-height: 400px;
  overflow: auto;
  font-size: 12px;
  margin: 0;
}
</style>
