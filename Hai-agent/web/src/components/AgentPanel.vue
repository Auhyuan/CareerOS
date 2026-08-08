<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue'
import {
  Bot,
  Brain,
  CheckCircle2,
  ClipboardList,
  FileQuestion,
  FileText,
  Map,
  MessageSquareText,
  Paperclip,
  Send,
  Sparkles,
  Upload,
  Wrench,
  X,
} from 'lucide-vue-next'

import {getNodeConversationHistory,streamNodeMessage,uploadFiles} from '../services/api'
import type {ConversationMessage,StreamEvent,TimelineItem,UploadedFile,WorkflowNode} from '../types'

const props=defineProps<{node:WorkflowNode|null}>()
const emit=defineEmits<{completed:[];openMap:[]}>()
const message=ref('')
const sending=ref(false)
const uploading=ref(false)
const historyLoading=ref(false)
const files=ref<UploadedFile[]>([])
const timeline=ref<TimelineItem[]>([])
const scrollArea=ref<HTMLElement|null>(null)
const isPreparationStage=computed(()=>props.node?.stage_code==='project_preparation')

watch(
  () => props.node?.node_id,
  async () => {
    timeline.value = []
    files.value = []
    message.value = ''

    if (props.node) {
      await loadConversationHistory(props.node)
    }
  },
  { immediate: true },
)

/** 将持久化历史消息转换为聊天时间线类型。 */
function historyMessageKind(message:ConversationMessage):TimelineItem['kind']{
  if(message.role==='user')return 'user'
  if(message.message_type.includes('reasoning'))return 'reasoning'
  if(message.role==='tool'||message.message_type.includes('tool'))return 'tool'
  return message.status==='success'?'answer':'error'
}

/** 返回历史消息中最适合展示的正文。 */
function historyMessageContent(message:ConversationMessage):string{
  if(message.content)return message.content
  if(message.structured_content)return JSON.stringify(message.structured_content,null,2)
  return message.error_message||''
}

/** 按节点绑定的 conversation_id 加载 AI 平台历史消息。 */
async function loadConversationHistory(node:WorkflowNode):Promise<void>{
  const requestedNodeId=node.node_id
  historyLoading.value=true

  try{
    const history=await getNodeConversationHistory(requestedNodeId)

    // 用户快速切换节点时，丢弃较早请求返回的数据，避免串到新节点。
    if(props.node?.node_id!==requestedNodeId)return

    timeline.value=history.messages
      .map((item)=>({
        id:item.message_id,
        kind:historyMessageKind(item),
        title:item.tool_name||undefined,
        content:historyMessageContent(item),
        detail:item.structured_content||undefined,
        state:item.status==='success'?'done':'error',
      } as TimelineItem))
      .filter((item)=>Boolean(item.content||item.detail))
  }catch(cause){
    if(props.node?.node_id!==requestedNodeId)return
    timeline.value.push({
      id:uid(),
      kind:'error',
      content:cause instanceof Error?cause.message:'历史消息加载失败',
    })
  }finally{
    if(props.node?.node_id===requestedNodeId)historyLoading.value=false
    void scrollToBottom()
  }
}
/** 生成前端时间线事件 ID。 */
function uid():string{
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

/** 滚动到当前对话底部。 */
async function scrollToBottom():Promise<void>{
  await nextTick()
  if(scrollArea.value)scrollArea.value.scrollTop=scrollArea.value.scrollHeight
}

/** 合并连续的模型增量，避免每个 token 生成一张卡片。 */
function appendDelta(kind:'reasoning'|'answer',content:string):void{
  const last=timeline.value.at(-1)
  if(last?.kind===kind)last.content+=content
  else timeline.value.push({id:uid(),kind,content})
}

/** 将后端 SSE 事件转换为业务时间线。 */
function handleEvent(event:StreamEvent):void{
  const data=event.data||{}
  if(event.type==='reasoning_delta')appendDelta('reasoning',String(data.content||''))
  else if(event.type==='model_delta')appendDelta('answer',String(data.content||''))
  else if(event.type==='tool_call'){
    timeline.value.push({
      id:uid(),kind:'tool',title:String(data.tool_name||'调用工具'),content:'正在执行',detail:data.args,state:'running',
    })
  }else if(event.type==='tool_result'){
    const running=[...timeline.value].reverse().find((item)=>item.kind==='tool'&&item.state==='running')
    if(running){
      running.state='done'
      running.content='执行完成'
      running.detail=data.result||data.content
    }else{
      timeline.value.push({id:uid(),kind:'tool',title:String(data.tool_name||'工具结果'),content:'执行完成',detail:data,state:'done'})
    }
  }else if(event.type==='error'){
    timeline.value.push({id:uid(),kind:'error',content:String(data.message||data.error||'Agent 执行失败')})
  }else if(event.type==='run_end'){
    timeline.value.push({id:uid(),kind:'status',content:data.status==='success'?'本轮处理完成':String(data.status||'运行结束')})
  }
  void scrollToBottom()
}

/** 把准备阶段的起步提示填入输入框，用户仍可继续补充具体信息。 */
function usePreparationStarter():void{
  message.value='我目前还没有完整的客户 Brief，请先根据我已有的信息帮我梳理项目准备清单，并告诉我最需要补充的一项信息。'
}

/** 上传用户选择的附件。 */
async function handleFiles(event:Event):Promise<void>{
  const input=event.target as HTMLInputElement
  const selected=Array.from(input.files||[])
  if(!selected.length)return
  uploading.value=true
  try{
    files.value.push(...await uploadFiles(selected))
  }catch(cause){
    timeline.value.push({id:uid(),kind:'error',content:cause instanceof Error?cause.message:'上传失败'})
  }finally{
    uploading.value=false
    input.value=''
  }
}

/** 删除尚未发送的附件。 */
function removeFile(fileId:string):void{
  files.value=files.value.filter((item)=>item.file_id!==fileId)
}

/** 发送消息并消费节点 Agent 的 SSE 输出。 */
async function send():Promise<void>{
  if(!props.node||sending.value||(!message.value.trim()&&!files.value.length))return
  const text=message.value.trim()
  const fileIds=files.value.map((item)=>item.file_id)
  timeline.value.push({id:uid(),kind:'user',content:text||`已上传 ${fileIds.length} 个附件`})
  message.value=''
  files.value=[]
  sending.value=true
  try{
    await streamNodeMessage({
      node_id:props.node.node_id,
      message:text,
      message_type:'text',
      payload:{},
      file_ids:fileIds,
      knowledge_base_ids:[],
    },handleEvent)
    emit('completed')
  }catch(cause){
    timeline.value.push({id:uid(),kind:'error',content:cause instanceof Error?cause.message:'Agent 调用失败'})
  }finally{
    sending.value=false
    void scrollToBottom()
  }
}
</script>

<template>
  <aside class="agent-panel">
    <header class="agent-header">
      <div class="agent-avatar"><Sparkles :size="19"/></div>
      <div>
        <strong>{{node?.title||'阶段 Agent'}}</strong>
        <span>{{node?`独立会话 · v${node.result_version}`:'请选择一个工作流节点'}}</span>
      </div>
      <div class="agent-header-actions"><span v-if="node" class="online-dot" title="Agent 可用"/><button class="map-trigger" type="button" :disabled="!node" title="打开方案演进地图" @click="emit('openMap')"><Map :size="16"/>方案地图</button></div>
    </header>

    <div ref="scrollArea" class="chat-scroll">
      <div v-if="historyLoading" class="history-loading"><i/><span>正在恢复阶段会话</span></div>
      <div v-if="!node" class="chat-empty">
        <Bot :size="28"/>
        <strong>选择一个阶段节点</strong>
        <p>查看阶段结果，或继续与该阶段 Agent 沟通。</p>
      </div>

      <section v-else-if="!historyLoading&&!timeline.length&&isPreparationStage" class="stage-guide">
        <header class="stage-guide-heading">
          <span><ClipboardList :size="19"/></span>
          <div>
            <p class="stage-guide-kicker">第一步 · 项目准备</p>
            <h2>先把已有资料交给 Agent</h2>
            <p>不要求一次准备完整。Agent 会先整理已知内容，再逐项确认缺失或冲突的信息。</p>
          </div>
        </header>

        <div class="guide-section">
          <h3><Upload :size="16"/>优先上传</h3>
          <ul>
            <li><strong>客户 Brief 或项目任务书</strong><span>活动背景、目标、时间、地点、预算等原始要求</span></li>
            <li><strong>品牌与产品资料</strong><span>品牌手册、产品介绍、传播口径和视觉规范</span></li>
            <li><strong>沟通记录</strong><span>会议纪要、访谈记录、聊天整理或客户反馈</span></li>
          </ul>
        </div>

        <div class="guide-section secondary-guide">
          <h3><FileQuestion :size="16"/>有这些也可以一起提供</h3>
          <p>历史活动方案、参考案例、场地资料、供应商限制、已有创意方向、受众信息及不可触碰事项。</p>
        </div>

        <div class="guide-callout">
          <CheckCircle2 :size="17"/>
          <p><strong>资料不完整也能开始。</strong>直接描述你已经知道的项目背景，Agent 每次只会追问一个最关键的问题。</p>
        </div>

        <button class="guide-starter" type="button" @click="usePreparationStarter">
          <MessageSquareText :size="16"/>没有完整 Brief，先开始梳理
        </button>
      </section>

      <div v-else-if="!historyLoading&&!timeline.length" class="chat-empty compact">
        <Bot :size="28"/>
        <strong>{{node.title}} Agent</strong>
        <p>{{node.summary||'告诉 Agent 当前阶段需要整理或修改的内容。'}}</p>
      </div>

      <div v-for="item in timeline" :key="item.id" class="timeline-item" :class="item.kind">
        <div v-if="item.kind==='reasoning'" class="timeline-icon"><Brain :size="15"/></div>
        <div v-else-if="item.kind==='tool'" class="timeline-icon"><Wrench :size="15"/></div>
        <div v-else-if="item.kind==='answer'" class="timeline-icon"><Sparkles :size="15"/></div>
        <div class="timeline-body">
          <strong v-if="item.title">{{item.title}}</strong>
          <span v-if="item.kind==='reasoning'" class="timeline-label">思考过程</span>
          <p>{{item.content}}</p>
          <details v-if="item.detail">
            <summary>查看详情</summary>
            <pre>{{JSON.stringify(item.detail,null,2)}}</pre>
          </details>
        </div>
      </div>
      <div v-if="sending" class="typing"><i/><i/><i/></div>
    </div>

    <footer class="composer" :class="{disabled:!node}">
      <div v-if="files.length" class="file-strip">
        <span v-for="file in files" :key="file.file_id">
          <FileText :size="14"/>{{file.original_name}}
          <button type="button" title="移除附件" @click="removeFile(file.file_id)"><X :size="13"/></button>
        </span>
      </div>
      <textarea
        v-model="message"
        :disabled="!node||sending"
        rows="3"
        :placeholder="isPreparationStage?'上传项目资料，或描述已知的客户需求…':'补充资料、提出修改意见，或让 Agent 整理当前阶段…'"
        @keydown.ctrl.enter="send"
      />
      <div class="composer-actions">
        <label class="icon-button" :class="{disabled:!node||uploading}" title="上传附件">
          <Paperclip :size="18"/>
          <input type="file" multiple hidden :disabled="!node||uploading" @change="handleFiles"/>
        </label>
        <span>{{uploading?'上传中':'Ctrl + Enter 发送'}}</span>
        <button class="send-button" type="button" title="发送消息" :disabled="!node||sending||(!message.trim()&&!files.length)" @click="send">
          <Send :size="17"/>
        </button>
      </div>
    </footer>
  </aside>
</template>
