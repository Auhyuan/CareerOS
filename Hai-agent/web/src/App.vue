<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {LoaderCircle,Plus,X} from 'lucide-vue-next'
import AgentPanel from './components/AgentPanel.vue';import AppDialogs from './components/AppDialogs.vue';import LoginView from './components/LoginView.vue';import ProjectSidebar from './components/ProjectSidebar.vue';import StageResultDialog from './components/StageResultDialog.vue';import StartNodeDialog from './components/StartNodeDialog.vue';import WorkflowTree from './components/WorkflowTree.vue'
import {advanceNode,clearTokens,createBranch,createBranchFromStart,createProject,getAccessToken,getMe,getProjectDetail,searchProjects} from './services/api'
import type {Project,ProjectDetail,User,WorkflowNode} from './types'
const user=ref<User|null>(null),projects=ref<Project[]>([]),detail=ref<ProjectDetail|null>(null),selectedNode=ref<WorkflowNode|null>(null),loading=ref(true),busy=ref(false),error=ref(''),createOpen=ref(false),branchNode=ref<WorkflowNode|null>(null),resultNode=ref<WorkflowNode|null>(null),startProject=ref<Project|null>(null),mapOpen=ref(false);const selectedProjectId=computed(()=>detail.value?.project.project_id||'')
/** 加载项目列表，并在需要时选中第一个项目。 */
async function loadProjects(preferredId=''):Promise<void>{const response=await searchProjects();projects.value=response.items;const target=preferredId||detail.value?.project.project_id||projects.value[0]?.project_id;if(target)await selectProject(target);else detail.value=null}
/** 查询并选中一个项目的完整工作流。 */
async function selectProject(projectId:string):Promise<void>{error.value='';mapOpen.value=false;detail.value=await getProjectDetail(projectId);selectedNode.value=detail.value.nodes.find((node)=>node.node_id===detail.value?.project.current_node_id)||detail.value.nodes.at(-1)||null}
/** 完成登录后进入工作台。 */
async function authenticated(currentUser:User):Promise<void>{user.value=currentUser;loading.value=true;try{await loadProjects()}catch(cause){showError(cause)}finally{loading.value=false}}
/** 统一展示业务错误。 */
function showError(cause:unknown):void{error.value=cause instanceof Error?cause.message:'操作失败';window.setTimeout(()=>{error.value=''},5000)}
/** 创建项目并切换到新项目。 */
async function handleCreateProject(body:Record<string,unknown>):Promise<void>{busy.value=true;try{const created=await createProject(body);createOpen.value=false;await loadProjects(created.project.project_id)}catch(cause){showError(cause)}finally{busy.value=false}}
/** 从历史节点创建新方案分支。 */
async function handleCreateBranch(body:Record<string,unknown>):Promise<void>{if(!detail.value)return;busy.value=true;try{await createBranch(body);branchNode.value=null;await selectProject(detail.value.project.project_id)}catch(cause){showError(cause)}finally{busy.value=false}}
/** 从虚拟开始节点创建新的项目准备路线。 */
async function handleCreateRootBranch(body:{project_id:string;branch_name:string}):Promise<void>{
  busy.value=true
  try{
    await createBranchFromStart(body)
    startProject.value=null
    mapOpen.value=false
    await selectProject(body.project_id)
  }catch(cause){showError(cause)}finally{busy.value=false}
}
/** 推进 ready 节点到固定的下一阶段。 */
async function handleAdvance(node:WorkflowNode):Promise<void>{if(!detail.value||!window.confirm(`确认完成“${node.title}”并进入下一阶段？`))return;busy.value=true;try{await advanceNode(node.node_id,node.result_version);await selectProject(detail.value.project.project_id)}catch(cause){showError(cause)}finally{busy.value=false}}
/** 从方案地图切换节点，并关闭地图以返回对应 Agent 会话。 */
function handleMapNodeSelect(node:WorkflowNode):void{selectedNode.value=node;mapOpen.value=false}
/** 从方案地图查看阶段结果。 */
function handleMapResult(node:WorkflowNode):void{mapOpen.value=false;resultNode.value=node}
/** 从方案地图创建历史分支。 */
function handleMapBranch(node:WorkflowNode):void{mapOpen.value=false;branchNode.value=node}
/** 从方案地图推进节点，并先关闭地图避免遮挡确认交互。 */
async function handleMapAdvance(node:WorkflowNode):Promise<void>{mapOpen.value=false;await handleAdvance(node)}
/** Agent 运行结束后刷新节点结果与状态。 */
async function refreshCurrentProject():Promise<void>{if(!detail.value)return;try{await selectProject(detail.value.project.project_id)}catch(cause){showError(cause)}}
/** 清除令牌并退出当前工作台。 */
function logout():void{clearTokens();user.value=null;projects.value=[];detail.value=null}
onMounted(async()=>{if(!getAccessToken()){loading.value=false;return}try{user.value=await getMe();await loadProjects()}catch{clearTokens();user.value=null}finally{loading.value=false}})
</script>
<template><div v-if="loading" class="app-loading"><LoaderCircle class="spin" :size="28"/><span>正在准备工作台</span></div><LoginView v-else-if="!user" @authenticated="authenticated"/><main v-else class="workspace-shell"><ProjectSidebar :projects="projects" :selected-id="selectedProjectId" :user="user" @select="selectProject" @create="createOpen=true" @logout="logout"/><AgentPanel :node="selectedNode" @open-map="mapOpen=true" @completed="refreshCurrentProject"/><div v-if="detail&&mapOpen" class="modal-backdrop workflow-map-backdrop" @mousedown.self="mapOpen=false"><section class="workflow-map-dialog" role="dialog" aria-modal="true" aria-label="方案演进地图"><button class="map-dialog-close icon-button" type="button" title="关闭方案地图" @click="mapOpen=false"><X :size="20"/></button><WorkflowTree :detail="detail" :selected-node-id="selectedNode?.node_id||''" @start-branch="startProject=detail.project" @select="handleMapNodeSelect" @result="handleMapResult" @branch="handleMapBranch" @advance="handleMapAdvance"/></section></div><div v-if="busy" class="busy-overlay"><LoaderCircle class="spin" :size="24"/>正在更新工作流</div><div v-if="error" class="toast-error">{{error}}</div><AppDialogs :create-open="createOpen" :branch-node="branchNode" @close-create="createOpen=false" @create-project="handleCreateProject" @close-branch="branchNode=null" @create-branch="handleCreateBranch"/><StageResultDialog :node="resultNode" @close="resultNode=null"/><StartNodeDialog :project="startProject" @close="startProject=null" @create="handleCreateRootBranch"/></main></template>