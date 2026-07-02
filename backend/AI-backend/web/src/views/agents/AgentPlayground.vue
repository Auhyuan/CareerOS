/**
 * 4. Agent Playground 试跑台
 * - 左侧：Agent 配置只读展示
 * - 右侧：输入 query + 流式对话
 * - 底部：结构化输出 JSON
 */
<template>
  <div>
    <h2 class="page-title">🧪 Playground - {{ agentDetail?.agent_name || agentId }}</h2>

    <a-row :gutter="16">
      <!-- 左侧 Agent 配置 -->
      <a-col :span="8">
        <a-card title="📋 Agent 配置" :loading="loading" class="side-card">
          <a-descriptions v-if="agentDetail" :column="1" size="small" bordered>
            <a-descriptions-item label="Agent ID">{{ agentDetail.agent_id }}</a-descriptions-item>
            <a-descriptions-item label="名称">{{ agentDetail.agent_name }}</a-descriptions-item>
            <a-descriptions-item label="模型">{{ agentDetail.config?.runtime_options?.model_code || '-' }}</a-descriptions-item>
            <a-descriptions-item label="温度">{{ agentDetail.config?.runtime_options?.temperature ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="超时(秒)">{{ agentDetail.config?.runtime_options?.timeout_seconds ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="工具">
              <a-tag v-for="t in agentDetail.config?.tools || []" :key="t" color="purple" class="mb-1">
                {{ t }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="可被 A2A 调用">
              <a-tag :color="agentDetail.config?.is_sub_agent ? 'green' : 'default'">
                {{ agentDetail.config?.is_sub_agent ? '是' : '否' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item v-if="agentDetail.config?.a2a?.sub_agent_list?.length" label="A2A 能力">
              <a-tag color="blue">已开启</a-tag>
            </a-descriptions-item>
          </a-descriptions>
          <a-empty v-else description="未加载到 Agent 配置" />

          <a-divider />

          <a-space direction="vertical" style="width: 100%">
            <div>
              <label>conversation_id</label>
              <a-input v-model:value="conversationId" placeholder="留空则自动生成" size="small" />
            </div>
            <div>
              <label>工具覆盖（覆盖默认）</label>
              <a-select
                v-model:value="overrideTools"
                mode="multiple"
                size="small"
                placeholder="不选则使用模板默认"
                :options="toolOptions"
                style="width: 100%"
                allow-clear
              />
            </div>
            <div>
              <a-checkbox v-model:checked="stream">流式输出</a-checkbox>
              <a-checkbox v-model:checked="memoryEnabled">长期记忆</a-checkbox>
              <a-checkbox v-model:checked="a2aEnabled">A2A 子 Agent</a-checkbox>
            </div>
            <a-button type="link" @click="router.push(`/agents/${agentId}/edit`)">✏️ 编辑该 Agent</a-button>
          </a-space>
        </a-card>
      </a-col>

      <!-- 右侧 对话区 -->
      <a-col :span="16">
        <a-card title="💬 对话">
          <!-- 消息流 -->
          <div class="message-area">
            <div v-for="(msg, i) in messages" :key="i" :class="['msg', `msg-${msg.role}`]">
              <div class="msg-meta">
                <a-tag :color="roleColor(msg.role)">{{ msg.role }}</a-tag>
                <span v-if="msg.tool_name" class="text-gray-500">🔧 {{ msg.tool_name }}</span>
                <span class="msg-time">{{ msg.time }}</span>
              </div>
              <div class="msg-content">{{ msg.content }}</div>

            </div>
            <a-empty v-if="!messages.length" description="开始一次对话吧" />
          </div>

          <!-- 输入区 -->
          <a-divider />
          <a-textarea
            v-model:value="input"
            :rows="3"
            placeholder="输入你的 query..."
            :disabled="running"
          />
          <div class="mt-2">
            <a-space>
              <a-button type="primary" :loading="running" @click="onRun">🚀 发送</a-button>
              <a-button @click="onClear">清空</a-button>
              <a-button @click="newConversation">新建会话</a-button>
            </a-space>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
/**
 * Playground 试跑台逻辑
 * - 加载 Agent 详情
 * - 支持流式（SSE）与非流式调用
 * - 消息流简单展示（不持久化）
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getAgentTemplateDetail, type AgentTemplate } from '@/api/agentTemplate'
import { getCapabilities } from '@/api/capabilities'
import { runAgent, runAgentStream } from '@/api/agentRun'

defineOptions({ name: 'AgentPlaygroundView' })

const route = useRoute()
const router = useRouter()
const agentId = computed(() => route.params.agent_id as string)

// 详情
const loading = ref(false)
const agentDetail = ref<AgentTemplate | null>(null)

// 工具选项
const toolOptions = ref<{ label: string; value: string }[]>([])

// 运行参数
const conversationId = ref<string>('')
const overrideTools = ref<string[]>([])
const stream = ref(true)
const memoryEnabled = ref(false)
const a2aEnabled = ref(false)
const running = ref(false)
const input = ref('')

// 消息流
interface MessageItem {
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  tool_name?: string
  time: string
}
const messages = ref<MessageItem[]>([])

/** 生成 uuid（占位） */
function uuid() {
  return 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
}

/** 加载详情与工具 */
async function loadAll() {
  loading.value = true
  try {
    agentDetail.value = await getAgentTemplateDetail(agentId.value)
    // 模板已配置 A2A 时自动开启
    if (agentDetail.value?.config?.a2a?.sub_agent_list?.length) {
      a2aEnabled.value = true
    }
    const cap = await getCapabilities()
    // 后端 registered_tools 是 string[]
    toolOptions.value = (cap.registered_tools || []).map((name) => ({ label: name, value: name }))
    if (!conversationId.value) conversationId.value = uuid()
  } finally {
    loading.value = false
  }
}

/** 发送运行请求 */
async function onRun() {
  if (!input.value.trim()) {
    message.warning('请输入 query')
    return
  }
  const userText = input.value
  messages.value.push({ role: 'user', content: userText, time: now() })
  input.value = ''
  running.value = true

  // 通过 agent_id 让后端读取模板配置；这里只传本次试跑需要覆盖的字段。
  const payload = {
    agent_id: agentId.value,
    query: userText,
    conversation_id: conversationId.value,
    tools: overrideTools.value.length ? overrideTools.value : undefined,
    optional_features: {
      long_term_memory_enabled: memoryEnabled.value,
    },
    a2a: a2aEnabled.value ? undefined : null,
  }

  try {
    if (stream.value) {
      // 流式：按 SSE 事件逐条渲染
      let answer = ''
      messages.value.push({ role: 'assistant', content: '', time: now() })
      const idx = messages.value.length - 1
      await runAgentStream(
        payload,
        (event) => {
          handleStreamEvent(event, idx, (delta) => {
            answer += delta
            messages.value[idx] = { ...messages.value[idx], content: answer }
          })
        },
        (err) => {
          message.error('流式调用失败：' + err.message)
          running.value = false
        },
        () => {
          running.value = false
        },
      )
    } else {
      // 非流式
      const res = await runAgent({ ...payload, stream: false })
      messages.value.push({ role: 'assistant', content: res.answer || '', time: now() })
      running.value = false
    }
  } catch (e) {
    running.value = false
    message.error('调用失败')
  }
}

/** 处理后端 SSE 事件，并把模型增量、工具事件和最终结果同步到消息流。 */
function handleStreamEvent(event: Record<string, any>, assistantIndex: number, appendDelta: (delta: string) => void) {
  const data = (event.data || {}) as Record<string, any>

  // 后端模型增量放在 data.content；这里兼容旧字段 delta/content，避免未来协议小调整导致空白。
  if (event.type === 'model_delta' || event.type === 'reasoning_delta') {
    const delta = String(data.content || event.delta || event.content || '')
    if (delta) appendDelta(delta)
    return
  }

  // messages 流中的 tool_call 表示模型发出了工具调用请求，不等同于工具执行开始或结束。
  if (event.type === 'tool_call') {
    messages.value.push({
      role: 'tool',
      tool_name: String(data.tool_name || 'tool'),
      content: `模型请求调用工具：${data.tool_name || 'tool'}\n参数：${safeJson(data.args)}`,
      time: now(),
    })
    return
  }

  // final 事件是后端最终答案兜底；部分模型或结构化输出场景可能没有稳定 token 增量。
  if (event.type === 'final') {
    const finalAnswer = String(data.answer || event.answer || '')
    if (finalAnswer) {
      messages.value[assistantIndex] = {
        ...messages.value[assistantIndex],
        content: finalAnswer,
      }
    }
    return
  }

  if (event.type === 'error') {
    messages.value[assistantIndex] = {
      ...messages.value[assistantIndex],
      content: `调用失败：${data.message || event.message || '未知错误'}`,
    }
  }
}

/** 安全格式化工具输入输出，避免复杂对象展示为 [object Object]。 */
function safeJson(value: unknown) {
  if (value === undefined || value === null || value === '') return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

/** 清空消息 */
function onClear() {
  messages.value = []
}

/** 新建会话 */
function newConversation() {
  conversationId.value = uuid()
  messages.value = []
  message.success('已新建会话：' + conversationId.value)
}

/** 时间 */
function now() {
  return new Date().toLocaleTimeString()
}

/** 角色颜色 */
function roleColor(r: string) {
  return r === 'user' ? 'blue' : r === 'assistant' ? 'green' : r === 'tool' ? 'purple' : 'default'
}

onMounted(loadAll)
</script>

<style scoped>
.page-title {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
}
.side-card {
  min-height: 600px;
}
.message-area {
  min-height: 400px;
  max-height: 540px;
  overflow-y: auto;
  padding: 8px 4px;
}
.msg {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fafafa;
}
.msg-user {
  background: #e6f4ff;
}
.msg-assistant {
  background: #f6ffed;
}
.msg-tool {
  background: #f9f0ff;
}
.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}
.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.msg-time {
  margin-left: auto;
}
pre {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
}
.mb-4 {
  margin-bottom: 16px;
}
.mb-1 {
  margin-bottom: 4px;
}
.mt-2 {
  margin-top: 8px;
}
</style>
