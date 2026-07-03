<!--
  Agent 调用页
  - 现代化聊天式调用界面
  - 顶部 Agent 选择器,中间聊天气泡,底部输入区
  - 渐变背景 + 卡片化设计 + 丰富空状态
-->
<template>
  <div class="invoke-page">
    <!-- 顶部:Agent 选择器与操作区 -->
    <div class="invoke-header">
      <div class="header-left">
        <div class="header-logo">🤖</div>
        <div class="header-title">
          <div class="title-main">Agent 调用台</div>
          <div class="title-sub">
            <span v-if="agentDetail" class="agent-info">
              <span class="status-dot" :class="`status-${agentDetail.status || 'active'}`"></span>
              当前 Agent: {{ agentName }}
            </span>
            <span v-else class="agent-info-placeholder">未选择 Agent</span>
          </div>
        </div>
      </div>
      <div class="header-right">
        <a-select
          v-model:value="selectedAgentId"
          show-search
          placeholder="切换 Agent 模板"
          class="agent-select"
          :options="agentOptions"
          :loading="agentListLoading"
          option-filter-prop="label"
          allow-clear
          @change="onAgentChange"
        >
          <template #suffixIcon><ApiOutlined /></template>
        </a-select>
        <a-tooltip title="新建会话">
          <a-button class="icon-btn" @click="newConversation">
            <template #icon><PlusOutlined /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip title="管理 Agent 模板">
          <a-button class="icon-btn" @click="router.push('/agents')">
            <template #icon><SettingOutlined /></template>
          </a-button>
        </a-tooltip>
      </div>
    </div>

    <!-- 消息区 -->
    <div ref="messageArea" class="message-area" @scroll="onAreaScroll">
      <!-- 漂亮空状态 -->
      <div v-if="!messages.length" class="empty-state">
        <div class="empty-icon-wrap">
          <div class="empty-icon">💬</div>
          <div class="empty-ripple"></div>
        </div>
        <h2 class="empty-title">
          {{ selectedAgentId ? '开始与 Agent 对话' : '先选择一个 Agent 模板' }}
        </h2>
        <p class="empty-desc">
          {{ selectedAgentId
            ? '在下方输入框提问, Agent 会自动调用配置的工具并回复'
            : '从右上角下拉框选择要调用的 Agent,即可开始对话' }}
        </p>
        <div v-if="!selectedAgentId" class="empty-suggestions">
          <a-button v-for="(g, gi) in agentOptions.slice(0, 3)" :key="gi" type="default" size="small" @click="onAgentChange(g.value)">
            {{ g.label }}
          </a-button>
        </div>
      </div>

      <!-- 消息流 -->
      <div class="messages-wrap">
        <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="['message', msg.role === 'user' ? 'message-user' : 'message-assistant']"
        >
          <div class="message-avatar">
            {{ msg.role === 'user' ? '👤' : '🤖' }}
          </div>
          <div class="message-body">
            <div class="message-meta">
              <span class="message-role">{{ msg.role === 'user' ? '我' : agentName }}</span>
              <span class="message-time">{{ msg.time }}</span>
            </div>
            <!-- Agent 流式时间线:按后端事件到达顺序渲染,保留 思考 -> 工具 -> 回复 的真实执行顺序 -->
            <template v-if="msg.role === 'assistant'">
              <div
                v-for="(block, bi) in msg.blocks"
                :key="`block-${i}-${bi}`"
              >
                <div v-if="block.type === 'reasoning'" class="message-reasoning">
                  <div class="reasoning-header">
                    <span class="reasoning-icon">💭</span>
                    <span class="reasoning-label">思考过程</span>
                  </div>
                  <div class="reasoning-content">{{ block.content }}</div>
                </div>

                <div v-else-if="block.type === 'tool'" class="message-tool-call">
                  <div class="tool-left">
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">{{ block.tool_name }}</span>
                    <span v-if="block.args && Object.keys(block.args).length" class="tool-args">
                      {{ formatToolArgs(block.args) }}
                    </span>
                    <a-tooltip
                      v-if="block.status === 'done' && block.output !== null && block.output !== undefined"
                      placement="topLeft"
                    >
                      <template #title>
                        <pre class="tool-output-pre">{{ formatToolOutput(block.output) }}</pre>
                      </template>
                      <span class="tool-output-hint">查看结果</span>
                    </a-tooltip>
                  </div>
                  <span class="tool-status">
                    <a-spin v-if="block.status === 'running'" size="small" />
                    <span v-else-if="block.status === 'done'" class="status-done">✓</span>
                    <span v-else-if="block.status === 'failed'" class="status-failed">✕</span>
                  </span>
                </div>

                <div v-else-if="block.type === 'content'" class="message-content">{{ block.content }}</div>
              </div>
            </template>
            <!-- 用户消息正文 -->
            <div v-else-if="msg.content" class="message-content">{{ msg.content }}</div>
            <!-- 元信息:耗时、回答长度、run_id 短码(完成时展示) -->
            <div
              v-if="(msg.elapsed_ms !== undefined || msg.answer_length !== undefined) && !running"
              class="message-meta-extras"
            >
              <span v-if="msg.elapsed_ms !== undefined" class="meta-chip">
                <ClockCircleOutlined /> {{ formatDuration(msg.elapsed_ms) }}
              </span>
              <span v-if="msg.answer_length !== undefined" class="meta-chip">
                📝 {{ msg.answer_length }} 字
              </span>
              <span v-if="msg.run_id" class="meta-chip meta-chip-id" :title="msg.run_id">
                #{{ msg.run_id.slice(0, 8) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 等待首个 token:打字指示器 -->
        <div v-if="waitingFirstToken" class="message message-assistant">
          <div class="message-avatar">🤖</div>
          <div class="message-body">
            <div class="message-meta">
              <span class="message-role">{{ agentName }}</span>
            </div>
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 回到最新按钮 -->
      <transition name="jump-fade">
        <div v-if="showJumpToBottom" class="jump-to-bottom" @click="scrollToBottomAndStick">
          <span class="jump-icon">↓</span>
          <span>回到最新</span>
        </div>
      </transition>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <div class="input-wrap">
        <a-textarea
          v-model:value="input"
          :rows="1"
          :auto-size="{ minRows: 1, maxRows: 6 }"
          placeholder="输入你的问题, Enter 发送, Shift+Enter 换行"
          :disabled="running || !selectedAgentId"
          class="chat-input"
          @pressEnter="onPressEnter"
        />
        <a-button
          type="primary"
          class="send-btn"
          :loading="running"
          :disabled="!selectedAgentId || !input.trim()"
          @click="onRun"
        >
          <template #icon v-if="!running"><SendOutlined /></template>
          {{ running ? '生成中' : '发送' }}
        </a-button>
      </div>
      <div class="input-hint">
        <span v-if="selectedAgentId" class="hint-active">
          <ThunderboltOutlined /> 当前会话 ID: {{ conversationId.slice(0, 16) }}...
        </span>
        <span v-else>👈 请先选择 Agent</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Agent 调用页
 * - 提供现代化聊天式调用体验
 * - 顶部选择 Agent, 下方连续对话
 * - 微吸: 用户在底部则吸底, 翻看历史则不打扰
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  ClockCircleOutlined,
  PlusOutlined,
  SettingOutlined,
  SendOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  getAgentTemplateDetail,
  searchAgentTemplates,
  type AgentTemplate,
} from '@/api/agentTemplate'
import { runAgentStream } from '@/api/agentRun'

defineOptions({ name: 'AgentInvokeView' })

const router = useRouter()
const route = useRoute()

// Agent 列表
const agentListLoading = ref(false)
const agentOptions = ref<{ label: string; value: string }[]>([])

// 当前选中的 Agent
const selectedAgentId = ref<string>('')
const agentDetail = ref<AgentTemplate | null>(null)
const agentName = ref<string>('Agent')

// 会话与运行
const conversationId = ref<string>('')
const input = ref('')
const running = ref(false)

/** Agent 流式展示块,用于按事件到达顺序渲染思考、工具调用和正式回复。 */
type StreamBlock = ReasoningBlock | ContentBlock | ToolCallBlock

/** 思考过程块。 */
interface ReasoningBlock {
  type: 'reasoning'
  content: string
}

/** 正式回复块。 */
interface ContentBlock {
  type: 'content'
  content: string
}

/** 单次工具调用块。 */
interface ToolCallBlock {
  type: 'tool'
  tool_name: string
  args: Record<string, unknown>
  /** 后端 tool_call 事件中的 id,用于和 tool_result.tool_call_id 匹配。 */
  call_id?: string | null
  /** 工具执行结果摘要(来自后端 tool_result.output), 仅作展示用。 */
  output: unknown
  status: 'running' | 'done' | 'failed'
}

interface MessageItem {
  role: 'user' | 'assistant'
  content: string
  reasoning: string
  tool_calls: ToolCallBlock[]
  /** Agent 流式时间线块,用于真实还原 思考 -> 工具 -> 回复 的执行顺序。 */
  blocks: StreamBlock[]
  time: string
  /** 本次 run 的 run_id,来自 run_start 事件 */
  run_id?: string
  /** 本次 run 的耗时(毫秒),来自 run_end 事件 */
  elapsed_ms?: number
  /** 本次 run 的回答长度,来自 run_end 事件 */
  answer_length?: number
}
const messages = ref<MessageItem[]>([])
const messageArea = ref<HTMLDivElement | null>(null)

/** 吸底开关 */
const stickToBottom = ref(true)

/** "回到最新"按钮展示条件 */
const showJumpToBottom = computed(() => {
  if (stickToBottom.value) return false
  if (!messageArea.value) return false
  return messageArea.value.scrollHeight > messageArea.value.clientHeight + 20
})

/** 距离底部多少像素以内算"在底部" */
const BOTTOM_THRESHOLD_PX = 40

/** 是否在等待首个 token */
const waitingFirstToken = computed(() => {
  if (!running.value) return false
  const last = messages.value[messages.value.length - 1]
  if (!last || last.role !== 'assistant') return true
  return !last.content && !last.reasoning
})

/** 生成临时会话 ID */
function uuid() {
  return 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
}

/** 加载 Agent 模板列表 */
async function loadAgentList() {
  agentListLoading.value = true
  try {
    const res = await searchAgentTemplates({ page: 1, page_size: 100 })
    agentOptions.value = (res.items || []).map((item) => ({
      label: `${item.agent_name} (${item.agent_id})`,
      value: item.agent_id,
    }))
  } finally {
    agentListLoading.value = false
  }
}

/** 加载选中的 Agent 详情 */
async function loadAgentDetail(agentId: string) {
  if (!agentId) {
    agentDetail.value = null
    agentName.value = 'Agent'
    return
  }
  try {
    agentDetail.value = await getAgentTemplateDetail(agentId)
    agentName.value = agentDetail.value?.agent_name || agentId
  } catch {
    agentName.value = agentId
  }
}

/** 选择器变化 */
function onAgentChange(agentId: string) {
  selectedAgentId.value = agentId
  messages.value = []
  input.value = ''
  stickToBottom.value = true
  if (!conversationId.value) {
    conversationId.value = uuid()
  }
  loadAgentDetail(agentId)
}

/** 新建会话 */
function newConversation() {
  conversationId.value = uuid()
  messages.value = []
  input.value = ''
  stickToBottom.value = true
  message.success('已新建会话')
}

/** 滚动到底部(只在 stickToBottom 时执行) */
async function scrollToBottom(force = false) {
  if (!force && !stickToBottom.value) return
  await nextTick()
  if (messageArea.value) {
    messageArea.value.scrollTop = messageArea.value.scrollHeight
  }
}

/** 用户主动点击"回到最新" */
function scrollToBottomAndStick() {
  stickToBottom.value = true
  scrollToBottom(true)
}

/** 监听消息区滚动 */
function onAreaScroll() {
  const el = messageArea.value
  if (!el) return
  const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  stickToBottom.value = distanceFromBottom <= BOTTOM_THRESHOLD_PX
}

/** 键盘发送 */
function onPressEnter(e: KeyboardEvent) {
  if (e.shiftKey) return  // Shift+Enter 换行
  e.preventDefault()
  onRun()
}

/** 当前时间 */
function now() {
  return new Date().toLocaleTimeString()
}

/** 格式化工具入参 */
function formatToolArgs(args: Record<string, unknown> | undefined | null): string {
  if (!args) return ''
  const keys = Object.keys(args)
  if (keys.length === 0) return ''
  try {
    return JSON.stringify(args)
  } catch {
    return keys.map((k) => `${k}=${String(args[k])}`).join(', ')
  }
}

/** 格式化工具结果输出, 控制在合理长度内, 用于 tooltip 展示 */
function formatToolOutput(output: unknown): string {
  try {
    const text = JSON.stringify(output, null, 2)
    // 超过 2000 字截断, 避免 tooltip 爆炸
    if (text.length > 2000) {
      return text.slice(0, 2000) + '\n... (truncated)'
    }
    return text
  } catch {
    return String(output)
  }
}

/** 智能格式化耗时: < 1s 用毫秒, < 1m 用秒, 否则用分秒 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = ((ms % 60_000) / 1000).toFixed(1)
  return `${minutes}m ${seconds}s`
}

/** 更新指定 assistant 消息。 */
function updateAssistantMessage(index: number, updater: (message: MessageItem) => MessageItem) {
  const current = messages.value[index]
  if (!current || current.role !== 'assistant') return
  messages.value[index] = updater(current)
}

/** 追加思考增量,连续思考会合并为同一个块。 */
function appendReasoningBlock(index: number, delta: string) {
  if (!delta) return
  updateAssistantMessage(index, (message) => {
    const blocks = [...message.blocks]
    const last = blocks[blocks.length - 1]
    if (last?.type === 'reasoning') {
      blocks[blocks.length - 1] = { ...last, content: last.content + delta }
    } else {
      blocks.push({ type: 'reasoning', content: delta })
    }
    return {
      ...message,
      reasoning: message.reasoning + delta,
      blocks,
    }
  })
}

/** 追加正式回复增量,连续回复会合并为同一个块。 */
function appendContentBlock(index: number, delta: string) {
  if (!delta) return
  updateAssistantMessage(index, (message) => {
    const blocks = [...message.blocks]
    const last = blocks[blocks.length - 1]
    if (last?.type === 'content') {
      blocks[blocks.length - 1] = { ...last, content: last.content + delta }
    } else {
      blocks.push({ type: 'content', content: delta })
    }
    return {
      ...message,
      content: message.content + delta,
      blocks,
    }
  })
}

/** 判断工具调用事件是否值得渲染,过滤模型工具调用分片里的空壳事件。 */
function isRenderableToolCallEvent(data: Record<string, any>): boolean {
  const toolName = String(data.tool_name || '')
  const args = data.args
  const hasRealToolName = toolName.length > 0 && toolName !== 'tool'
  const hasObjectArgs = !!args && typeof args === 'object' && !Array.isArray(args)

  // LangChain 的 tool_call_chunks 可能会把参数按字符串碎片流出, 例如 "{"、"\"name\": ..."。
  // 这类事件只代表模型正在拼工具参数,不是一次完整工具调用,前端不展示。
  return hasRealToolName && hasObjectArgs
}

/** 记录一次工具调用,并按到达顺序加入时间线。 */
function appendToolCallBlock(index: number, data: Record<string, any>) {
  if (!isRenderableToolCallEvent(data)) return

  const callId = typeof data.id === 'string' ? data.id : null
  const args = (data.args as Record<string, unknown>) || {}
  const toolBlock: ToolCallBlock = {
    type: 'tool',
    tool_name: String(data.tool_name || 'tool'),
    args,
    call_id: callId,
    output: null,
    status: 'running',
  }

  updateAssistantMessage(index, (message) => {
    // 同一个 tool_call_id 可能被流式分片多次推送,这里更新同一个工具块,避免页面散成多张卡片。
    if (callId) {
      const blocks = [...message.blocks]
      const blockIndex = blocks.findIndex((block) => block.type === 'tool' && block.call_id === callId)
      const callIndex = message.tool_calls.findIndex((call) => call.call_id === callId)
      if (blockIndex >= 0) {
        const oldBlock = blocks[blockIndex] as ToolCallBlock
        const nextBlock: ToolCallBlock = {
          ...oldBlock,
          tool_name: toolBlock.tool_name || oldBlock.tool_name,
          args: Object.keys(args).length ? args : oldBlock.args,
          status: oldBlock.status === 'done' ? 'done' : 'running',
        }
        blocks[blockIndex] = nextBlock
        const tool_calls = message.tool_calls.map((call, currentIndex) =>
          currentIndex === callIndex ? nextBlock : call,
        )
        return { ...message, tool_calls, blocks }
      }
    }

    return {
      ...message,
      tool_calls: [...message.tool_calls, toolBlock],
      blocks: [...message.blocks, toolBlock],
    }
  })
}

/** 回填工具执行结果,优先按 tool_call_id 匹配,否则匹配最后一个运行中的工具块。 */
function finishToolCallBlock(index: number, data: Record<string, any>) {
  updateAssistantMessage(index, (message) => {
    const callId = typeof data.tool_call_id === 'string' ? data.tool_call_id : null
    const blocks = message.blocks.map((block) => ({ ...block })) as StreamBlock[]
    const toolIndexes = blocks
      .map((block, blockIndex) => ({ block, blockIndex }))
      .filter((item): item is { block: ToolCallBlock; blockIndex: number } => item.block.type === 'tool')

    const matched = callId
      ? toolIndexes.find((item) => item.block.call_id === callId)
      : [...toolIndexes].reverse().find((item) => item.block.status === 'running')
    const target = matched || toolIndexes[toolIndexes.length - 1]

    if (!target) return message

    const nextToolBlock: ToolCallBlock = {
      ...target.block,
      tool_name: String(data.tool_name || target.block.tool_name || 'tool'),
      status: 'done',
      output: data.output ?? null,
    }
    blocks[target.blockIndex] = nextToolBlock

    const toolCallIndex = (() => {
      if (nextToolBlock.call_id) {
        return message.tool_calls.findIndex((call) => call.call_id === nextToolBlock.call_id)
      }
      const runningIndex = message.tool_calls.findLastIndex((call) => call.status === 'running')
      return runningIndex >= 0 ? runningIndex : message.tool_calls.length - 1
    })()
    const tool_calls = message.tool_calls.map((call, callIndex) =>
      callIndex === toolCallIndex ? nextToolBlock : call,
    )

    return {
      ...message,
      tool_calls,
      blocks,
    }
  })
}

/** 把指定 assistant 消息中仍在运行的工具块标记为目标状态。 */
function markRunningTools(index: number, status: 'done' | 'failed') {
  updateAssistantMessage(index, (message) => {
    const blocks = message.blocks.map((block) => {
      if (block.type === 'tool' && block.status === 'running') {
        return { ...block, status }
      }
      return block
    }) as StreamBlock[]
    const tool_calls = message.tool_calls.map((call) =>
      call.status === 'running' ? { ...call, status } : call,
    )
    return { ...message, blocks, tool_calls }
  })
}

/** 发送运行请求 */
async function onRun() {
  if (!selectedAgentId.value) {
    message.warning('请先选择一个 Agent')
    return
  }
  const text = input.value.trim()
  if (!text) {
    message.warning('请输入问题')
    return
  }

  messages.value.push({ role: 'user', content: text, reasoning: '', tool_calls: [], blocks: [], time: now() })
  input.value = ''
  running.value = true
  stickToBottom.value = true
  await scrollToBottom(true)

  const payload = {
    agent_id: selectedAgentId.value,
    query: text,
    conversation_id: conversationId.value,
  }

  try {
    messages.value.push({ role: 'assistant', content: '', reasoning: '', tool_calls: [], blocks: [], time: now() })
    const idx = messages.value.length - 1
    await runAgentStream(
      payload,
      (event) => {
        const data = (event.data || {}) as Record<string, any>

        // 生命周期:运行开始 - 拿到 run_id
        if (event.type === 'run_start') {
          if (data.run_id) {
            // 在最后一条 assistant 消息里记录 run_id, 方便后续做"查看链路"操作
            const last = messages.value[idx]
            if (last) {
              messages.value[idx] = { ...last, run_id: String(data.run_id) }
            }
          }
          return
        }

        // 生命周期:Agent 装配完成 - 可选展示,这里只在调试态记录
        if (event.type === 'agent_assembled') {
          // 普通聊天界面不展示,保持界面简洁
          // 如需展示可在 console 打印或塞入 metadata
          return
        }

        // 工具调用:模型发起一次新工具调用,按事件顺序加入时间线。
        if (event.type === 'tool_call') {
          appendToolCallBlock(idx, data)
          scrollToBottom()
          return
        }

        // 工具结果:回填对应工具块,不进入正式回复正文。
        if (event.type === 'tool_result') {
          finishToolCallBlock(idx, data)
          scrollToBottom()
          return
        }

        // 思考过程:reasoning_delta 按顺序追加到时间线,连续思考自动合并。
        if (event.type === 'reasoning_delta') {
          const delta = String(data.content || event.delta || event.content || '')
          appendReasoningBlock(idx, delta)
          scrollToBottom()
          return
        }

        // 正式回复:model_delta 按顺序追加到时间线,连续回复自动合并。
        if (event.type === 'model_delta') {
          const delta = String(data.content || event.delta || event.content || '')
          appendContentBlock(idx, delta)
          scrollToBottom()
          return
        }

        // 生命周期:运行结束 - 标记完成, 记录耗时
        if (event.type === 'run_end') {
          markRunningTools(idx, 'done')
          const last = messages.value[idx]
          if (last) {
            messages.value[idx] = {
              ...last,
              elapsed_ms: typeof data.elapsed_ms === 'number' ? data.elapsed_ms : undefined,
              answer_length: typeof data.answer_length === 'number' ? data.answer_length : undefined,
            }
          }
          running.value = false
          return
        }

        // 错误:展示错误信息, 关闭 loading
        if (event.type === 'error') {
          messages.value[idx] = {
            ...messages.value[idx],
            content: messages.value[idx].content
              ? messages.value[idx].content + `\n\n[错误] ${data.message || event.message || '未知错误'}`
              : `[错误] ${data.message || event.message || '未知错误'}`,
          }
          // 错误时把未完成的工具调用标为 failed。
          markRunningTools(idx, 'failed')
          running.value = false
        }
      },
      (err) => {
        message.error('流式调用失败:' + err.message)
        running.value = false
      },
      () => {
        // 兜底:网络流结束时确保 loading 关闭
        markRunningTools(idx, 'done')
        running.value = false
        scrollToBottom()
      },
    )
  } catch (e) {
    running.value = false
    message.error('调用失败')
  }
}

onMounted(async () => {
  await loadAgentList()
  const queryAgentId = route.query.agent_id as string
  if (queryAgentId) {
    selectedAgentId.value = queryAgentId
    await loadAgentDetail(queryAgentId)
  }
})
</script>

<style scoped>
/* ========== 整体页面 ========== */
.invoke-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 112px);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf3 100%);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

/* ========== 顶部 Header ========== */
.invoke-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  z-index: 10;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-logo {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}
.header-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.title-main {
  font-size: 16px;
  font-weight: 600;
  color: #1f1f1f;
  letter-spacing: 0.3px;
}
.title-sub {
  font-size: 12px;
  color: #8c8c8c;
}
.agent-info {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.agent-info-placeholder {
  color: #bfbfbf;
}
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
  animation: pulse 2s infinite;
}
.status-dot.status-disabled {
  background: #bfbfbf;
  box-shadow: 0 0 0 2px rgba(191, 191, 191, 0.2);
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2); }
  50% { box-shadow: 0 0 0 4px rgba(82, 196, 26, 0.1); }
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.agent-select {
  width: 240px;
}
.icon-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

/* ========== 消息区 ========== */
.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  position: relative;
}
.message-area::-webkit-scrollbar {
  width: 6px;
}
.message-area::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}
.message-area::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
.messages-wrap {
  max-width: 860px;
  margin: 0 auto;
}

/* ========== 漂亮空状态 ========== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
  text-align: center;
  padding: 0 24px;
}
.empty-icon-wrap {
  position: relative;
  margin-bottom: 24px;
}
.empty-icon {
  font-size: 56px;
  position: relative;
  z-index: 2;
  animation: float 3s ease-in-out infinite;
}
.empty-ripple {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  opacity: 0.08;
  z-index: 1;
  animation: ripple 2.5s ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
@keyframes ripple {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.08; }
  50% { transform: translate(-50%, -50%) scale(1.3); opacity: 0.04; }
}
.empty-title {
  font-size: 22px;
  font-weight: 600;
  color: #1f1f1f;
  margin: 0 0 8px;
}
.empty-desc {
  font-size: 14px;
  color: #8c8c8c;
  margin: 0 0 24px;
  max-width: 400px;
  line-height: 1.6;
}
.empty-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

/* ========== 消息气泡 ========== */
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  animation: messageIn 0.3s ease-out;
}
@keyframes messageIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.message-user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f2f5 0%, #e6e9ed 100%);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  font-size: 18px;
  flex-shrink: 0;
}
.message-user .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}
.message-body {
  background: #fff;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  max-width: calc(100% - 60px);
  min-width: 60px;
}
.message-user .message-body {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
  color: #8c8c8c;
}
.message-user .message-meta {
  color: rgba(255, 255, 255, 0.85);
}
.message-role {
  font-weight: 500;
}
.message-time {
  margin-left: auto;
}

/* ========== 思考过程 ========== */
.message-reasoning {
  margin-bottom: 10px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #fafbfc 0%, #f5f6f8 100%);
  border-left: 3px solid #b37feb;
  border-radius: 6px;
  font-size: 12px;
  color: #595959;
  line-height: 1.7;
}
.reasoning-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.reasoning-icon {
  font-size: 13px;
}
.reasoning-label {
  font-size: 11px;
  color: #b37feb;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.reasoning-content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ========== 工具调用 ========== */
.message-tool-call {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: linear-gradient(135deg, #e6f4ff 0%, #f0f9ff 100%);
  border: 1px solid #91caff;
  border-radius: 8px;
  font-size: 12px;
  color: #003a8c;
}
.tool-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}
.tool-icon {
  font-size: 13px;
}
.tool-name {
  font-weight: 600;
  color: #0958d9;
}
.tool-args {
  color: #595959;
  font-family: 'Fira Code', 'Cascadia Code', Menlo, Consolas, monospace;
  font-size: 11px;
  word-break: break-all;
}
.tool-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-weight: 600;
  font-size: 11px;
  flex-shrink: 0;
}
.status-done {
  color: #52c41a;
}
.status-failed {
  color: #ff4d4f;
}
.tool-output-hint {
  display: inline-block;
  margin-left: 4px;
  padding: 1px 6px;
  font-size: 10px;
  color: #1677ff;
  background: rgba(22, 119, 255, 0.08);
  border-radius: 4px;
  cursor: help;
}
.tool-output-pre {
  margin: 0;
  max-width: 480px;
  max-height: 360px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Fira Code', 'Cascadia Code', Menlo, Consolas, monospace;
}

/* ========== 消息元信息 chip ========== */
.message-meta-extras {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #f0f0f0;
  flex-wrap: wrap;
}
.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  font-size: 11px;
  color: #8c8c8c;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  white-space: nowrap;
}
.meta-chip-id {
  font-family: 'Fira Code', Menlo, Consolas, monospace;
  color: #1677ff;
  background: #e6f4ff;
  border-color: #91caff;
  cursor: help;
}

/* ========== 正式回复 ========== */
.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  font-size: 14px;
  color: #1f1f1f;
}
.message-user .message-content {
  color: #fff;
}

/* ========== 打字指示器 ========== */
.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}
.typing-indicator span {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  animation: typingBounce 1.4s ease-in-out infinite;
}
.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* ========== 回到最新按钮 ========== */
.jump-to-bottom {
  position: sticky;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: fit-content;
  margin: 8px auto 0;
  padding: 6px 16px;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 18px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  font-size: 12px;
  color: #1677ff;
  cursor: pointer;
  user-select: none;
  z-index: 2;
  transition: all 0.2s;
}
.jump-to-bottom:hover {
  background: #e6f4ff;
  border-color: #91caff;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(22, 119, 255, 0.15);
}
.jump-icon {
  font-size: 14px;
  font-weight: 600;
}
.jump-fade-enter-active,
.jump-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.jump-fade-enter-from,
.jump-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* ========== 输入区 ========== */
.input-area {
  padding: 16px 24px 20px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  z-index: 10;
}
.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  max-width: 860px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 16px;
  padding: 8px 8px 8px 16px;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.input-wrap:hover {
  border-color: #91caff;
}
.input-wrap:focus-within {
  border-color: #1677ff;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.1);
}
.chat-input {
  flex: 1;
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 8px 0 !important;
  resize: none !important;
}
.chat-input :deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  background: transparent !important;
}
.send-btn {
  height: 36px;
  min-width: 80px;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  font-weight: 500;
}
.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #5568d3 0%, #6a3f9c 100%) !important;
}
.send-btn:disabled {
  background: #f5f5f5 !important;
  color: #bfbfbf !important;
  border: none;
}
.input-hint {
  max-width: 860px;
  margin: 8px auto 0;
  font-size: 12px;
  color: #8c8c8c;
  text-align: center;
}
.hint-active {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>
