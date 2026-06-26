/**
 * Vue Router 路由配置
 * 10 个核心页面 + 原有示例页
 */
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import type { LayoutKey } from '@/layouts/registry'
import Home from '@/views/Home.vue'

const history = createWebHashHistory()

type RouteWithLayoutMeta = Omit<RouteRecordRaw, 'meta'> & {
  meta: {
    layout: LayoutKey
    title?: string
  }
}

const routes = [
  // 1. Dashboard 首页
  {
    path: '/',
    name: 'Dashboard',
    component: Home,
    meta: { layout: 'default', title: 'Dashboard' },
  },
  // 2. Agent 模板管理列表
  {
    path: '/agents',
    name: 'AgentList',
    component: () => import('@/views/agents/AgentList.vue'),
    meta: { layout: 'default', title: 'Agent 模板' },
  },
  // 3. Agent 模板编辑 - 创建
  {
    path: '/agents/create',
    name: 'AgentCreate',
    component: () => import('@/views/agents/AgentEdit.vue'),
    meta: { layout: 'default', title: '新建 Agent' },
  },
  // 3. Agent 模板编辑 - 编辑
  {
    path: '/agents/:agent_id/edit',
    name: 'AgentEdit',
    component: () => import('@/views/agents/AgentEdit.vue'),
    meta: { layout: 'default', title: '编辑 Agent' },
  },
  // 4. Agent Playground 试跑台
  {
    path: '/agents/:agent_id/playground',
    name: 'AgentPlayground',
    component: () => import('@/views/agents/AgentPlayground.vue'),
    meta: { layout: 'default', title: 'Playground' },
  },
  // 5. 会话历史列表
  {
    path: '/conversations',
    name: 'ConversationList',
    component: () => import('@/views/conversations/ConversationList.vue'),
    meta: { layout: 'default', title: '会话历史' },
  },
  // 6. 会话详情
  {
    path: '/conversations/:conversation_id',
    name: 'ConversationDetail',
    component: () => import('@/views/conversations/ConversationDetail.vue'),
    meta: { layout: 'default', title: '会话详情' },
  },
  // 7. Agent 运行监控
  {
    path: '/runs',
    name: 'RunMonitor',
    component: () => import('@/views/runs/RunMonitor.vue'),
    meta: { layout: 'default', title: '运行监控' },
  },
  // 8. 工具管理
  {
    path: '/tools',
    name: 'ToolManager',
    component: () => import('@/views/tools/ToolManager.vue'),
    meta: { layout: 'default', title: '工具管理' },
  },
  // 9. 模型配置
  {
    path: '/settings/model',
    name: 'ModelConfig',
    component: () => import('@/views/settings/ModelConfig.vue'),
    meta: { layout: 'default', title: '模型配置' },
  },
  // 10. A2A 可视化
  {
    path: '/a2a',
    name: 'A2AVisualizer',
    component: () => import('@/views/a2a/A2AVisualizer.vue'),
    meta: { layout: 'default', title: 'A2A 拓扑' },
  },
  // 保留示例页
  {
    path: '/empty',
    name: 'Empty',
    component: () => import('@/views/Empty.vue'),
    meta: { layout: 'empty', title: 'Empty' },
  },
] satisfies RouteWithLayoutMeta[]

const router = createRouter({
  linkActiveClass: 'active',
  history,
  routes,
})

export { router }
