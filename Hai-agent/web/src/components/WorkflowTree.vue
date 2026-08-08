<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, Bot, Check, Eye, GitBranch, Plus, RotateCcw } from 'lucide-vue-next'
import type { CSSProperties } from 'vue'
import type { ProjectDetail, WorkflowNode } from '../types'

interface GraphNodePoint{node:WorkflowNode;x:number;y:number;depth:number}
interface GraphEdge{key:string;x1:number;y1:number;x2:number;y2:number}

const props=defineProps<{detail:ProjectDetail;selectedNodeId:string}>()
const emit=defineEmits<{startBranch:[];select:[node:WorkflowNode];result:[node:WorkflowNode];branch:[node:WorkflowNode];advance:[node:WorkflowNode]}>()

const stageLabels:Record<string,string>={
  project_preparation:'项目准备',
  requirement_confirmation:'需求确认',
  creative_direction:'策划方向',
  proposal_generation:'方案生成',
  feedback_revision:'反馈修改',
}

const stageDepths:Record<string,number>={
  project_preparation:1,
  requirement_confirmation:2,
  creative_direction:3,
  proposal_generation:4,
  feedback_revision:5,
}

const branchNames=computed(()=>new Map(props.detail.branches.map((branch)=>[branch.branch_id,branch.is_main?'主线方案':branch.name])))

/** 根据业务阶段计算横向层级，并根据 parent_node_id 建立具体节点连线。 */
const graphLayout=computed(()=>{
  const nodes=props.detail.nodes

  const depthGroups=new Map<number,WorkflowNode[]>()
  for(const node of nodes){
    // 同一业务阶段必须处于同一列；未知阶段放到现有阶段之后，避免覆盖。
    const depth=stageDepths[node.stage_code]||6
    const group=depthGroups.get(depth)||[]
    group.push(node)
    depthGroups.set(depth,group)
  }

  const maxDepth=Math.max(1,...depthGroups.keys())
  const maxGroupSize=Math.max(1,...Array.from(depthGroups.values()).map((group)=>group.length))
  const width=Math.max(1080,360+maxDepth*260)
  const height=Math.max(560,160+maxGroupSize*190)
  const start={x:90,y:height/2}
  const points:GraphNodePoint[]=[]

  for(const [depth,group] of depthGroups){
    group.sort((first,second)=>first.created_at.localeCompare(second.created_at))
    group.forEach((node,index)=>{
      points.push({
        node,
        depth,
        x:100+depth*260,
        y:(index+1)*height/(group.length+1),
      })
    })
  }

  const pointMap=new Map(points.map((point)=>[point.node.node_id,point]))
  const edges:GraphEdge[]=points.map((point)=>{
    // 每条路线的项目准备节点都直接从虚拟“开始”节点发出。
    const isPreparation=point.node.stage_code==='project_preparation'
    const parent=!isPreparation&&point.node.parent_node_id
      ?pointMap.get(point.node.parent_node_id)
      :null
    return {
      key:(parent?.node.node_id||'start')+'-'+point.node.node_id,
      x1:parent?parent.x:start.x,
      y1:parent?parent.y:start.y,
      x2:point.x,
      y2:point.y,
    }
  })

  return {width,height,start,points,edges}
})

/** 返回节点阶段的中文名称。 */
function stageLabel(node:WorkflowNode):string{return stageLabels[node.stage_code]||node.title}
/** 返回节点状态的中文标签。 */
function statusLabel(status:string):string{return ({working:'进行中',ready:'待确认',completed:'已完成',cancelled:'已取消'} as Record<string,string>)[status]||status}
/** 判断节点是否已经保存了可查看的阶段结果。 */
function hasStageResult(node:WorkflowNode):boolean{return node.result_version>0&&Object.keys(node.result_data||{}).length>0}
/** 把计算后的节点坐标转换为绝对定位样式。 */
function pointStyle(point:GraphNodePoint):CSSProperties{return {left:point.x+'px',top:point.y+'px'}}
</script>

<template>
  <section class="workflow-area tree-map">
    <header class="map-project-header">
      <div>
        <span class="map-eyebrow">{{detail.project.event_type||'活动策划'}}</span>
        <h1>{{detail.project.name}}</h1>
        <p>从开始节点创建新路线，或点击任意历史节点进入对应的独立 Agent 会话。</p>
      </div>
      <div class="map-current">
        <GitBranch :size="15"/>
        <span>当前阶段</span>
        <strong>{{stageLabels[detail.project.current_stage]||detail.project.current_stage}}</strong>
      </div>
    </header>

    <div class="tree-map-legend">
      <span><i class="working"/>进行中</span>
      <span><i class="ready"/>待确认</span>
      <span><i class="completed"/>已完成</span>
      <small>悬停节点可查看操作</small>
    </div>

    <div class="tree-canvas-scroll">
      <div class="tree-canvas" :style="{width:graphLayout.width+'px',height:graphLayout.height+'px'}">
        <svg class="tree-edges" :viewBox="'0 0 '+graphLayout.width+' '+graphLayout.height" aria-hidden="true">
          <defs>
            <marker id="tree-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z"/>
            </marker>
          </defs>
          <path
            v-for="edge in graphLayout.edges"
            :key="edge.key"
            :d="'M '+edge.x1+' '+edge.y1+' C '+(edge.x1+90)+' '+edge.y1+', '+(edge.x2-90)+' '+edge.y2+', '+edge.x2+' '+edge.y2"
            marker-end="url(#tree-arrow)"
          />
        </svg>

        <article class="start-node" :style="{left:graphLayout.start.x+'px',top:graphLayout.start.y+'px'}">
          <div class="start-orb">开始</div>
          <div class="start-node-action">
            <button type="button" @click="emit('startBranch')"><Plus :size="14"/>新起节点</button>
          </div>
        </article>

        <article
          v-for="point in graphLayout.points"
          :key="point.node.node_id"
          class="tree-node"
          :class="[point.node.status,{selected:point.node.node_id===selectedNodeId,current:point.node.node_id===detail.project.current_node_id}]"
          :style="pointStyle(point)"
        >
          <button class="tree-node-orb" type="button" @click="emit('select',point.node)">
            <Check v-if="point.node.status==='completed'" :size="18"/>
            <span v-else>{{point.node.sequence_no}}</span>
          </button>

          <div class="tree-node-card" @click="emit('select',point.node)">
            <span class="tree-node-stage"><Bot :size="12"/>{{stageLabel(point.node)}}</span>
            <strong>{{point.node.title}}</strong>
            <p>{{point.node.summary||'等待 Agent 整理阶段结果'}}</p>
            <div class="tree-node-meta">
              <span>{{branchNames.get(point.node.branch_id)||'方案路线'}}</span>
              <small>{{statusLabel(point.node.status)}} · v{{point.node.result_version}}</small>
            </div>
            <div class="tree-node-actions" @click.stop>
              <button v-if="hasStageResult(point.node)" class="mini-action result-action" type="button" @click="emit('result',point.node)"><Eye :size="13"/>结果</button>
              <button v-if="['ready','completed'].includes(point.node.status)" class="mini-action" type="button" @click="emit('branch',point.node)"><RotateCcw :size="13"/>分支</button>
              <button v-if="point.node.status==='ready'&&point.node.node_id===detail.project.current_node_id" class="mini-action strong" type="button" @click="emit('advance',point.node)"><ArrowRight :size="13"/>推进</button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
