<script setup lang="ts">
import { ref, watch } from 'vue'
import { GitBranch, X } from 'lucide-vue-next'

import type { Project } from '../types'

const props=defineProps<{project:Project|null}>()
const emit=defineEmits<{close:[];create:[body:{project_id:string;branch_name:string}]}>()
const branchName=ref('')

watch(()=>props.project?.project_id,()=>{
  branchName.value=props.project?'新方案路线':''
})

/** 提交从项目开始节点创建的新根路线。 */
function submit():void{
  if(!props.project||!branchName.value.trim())return
  emit('create',{project_id:props.project.project_id,branch_name:branchName.value.trim()})
}
</script>

<template>
  <div v-if="project" class="modal-backdrop" @mousedown.self="emit('close')">
    <section class="modal compact-modal" role="dialog" aria-modal="true" aria-label="新起项目节点">
      <header>
        <div>
          <span class="modal-icon"><GitBranch :size="18"/></span>
          <div>
            <h2>从开始节点新起路线</h2>
            <p>创建新的“项目准备”节点，并使用独立 Agent 会话。</p>
          </div>
        </div>
        <button class="icon-button" type="button" title="关闭" @click="emit('close')"><X :size="18"/></button>
      </header>
      <label>路线名称<input v-model="branchName" autofocus placeholder="例如：备选创意路线"/></label>
      <footer>
        <button class="secondary" type="button" @click="emit('close')">取消</button>
        <button class="primary" type="button" :disabled="!branchName.trim()" @click="submit">创建节点</button>
      </footer>
    </section>
  </div>
</template>
