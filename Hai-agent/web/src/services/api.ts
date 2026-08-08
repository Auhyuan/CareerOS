import type {NodeConversationHistory,ProjectDetail,ProjectList,Result,StreamEvent,TokenPair,UploadedFile,User} from '../types'
const ACCESS_TOKEN_KEY='hai_access_token'
const REFRESH_TOKEN_KEY='hai_refresh_token'
/** 读取本地 Access Token。 */
export function getAccessToken():string{return localStorage.getItem(ACCESS_TOKEN_KEY)||''}
/** 保存登录令牌。 */
export function saveTokens(tokens:TokenPair):void{localStorage.setItem(ACCESS_TOKEN_KEY,tokens.access_token);localStorage.setItem(REFRESH_TOKEN_KEY,tokens.refresh_token)}
/** 清理登录令牌。 */
export function clearTokens():void{localStorage.removeItem(ACCESS_TOKEN_KEY);localStorage.removeItem(REFRESH_TOKEN_KEY)}
/** 调用 Hai-agent JSON API，并处理统一 Result 响应。 */
async function request<T>(path:string,body:unknown,authenticated=true):Promise<T>{const headers:Record<string,string>={'Content-Type':'application/json'};if(authenticated&&getAccessToken())headers.Authorization=`Bearer ${getAccessToken()}`;const response=await fetch(`/api${path}`,{method:'POST',headers,body:JSON.stringify(body)});const payload=await response.json() as Result<T>;if(payload.code!==0)throw new Error(payload.msg||'请求失败');return payload.data}
/** 登录并返回双令牌。 */
export function login(username:string,password:string):Promise<TokenPair>{return request('/auth/login',{username,password},false)}
/** 注册本地用户。 */
export function register(username:string,password:string,email?:string):Promise<User>{return request('/auth/register',{username,password,email:email||null},false)}
/** 查询当前登录用户。 */
export function getMe():Promise<User>{return request('/auth/me',{})}
/** 查询当前用户的项目列表。 */
export function searchProjects(keyword=''):Promise<ProjectList>{return request('/projects/search',{keyword:keyword||null,page:1,page_size:100})}
/** 创建项目并返回完整项目图。 */
export function createProject(body:Record<string,unknown>):Promise<ProjectDetail>{return request('/projects/create',body)}
/** 查询项目、分支和节点详情。 */
export function getProjectDetail(projectId:string):Promise<ProjectDetail>{return request('/projects/detail',{project_id:projectId})}
/** 从项目虚拟开始节点创建新的根路线。 */
export function createBranchFromStart(body:{project_id:string;branch_name:string}):Promise<unknown>{return request('/workflow/branches/create-from-start',body)}
/** 从历史节点创建独立分支。 */
export function createBranch(body:Record<string,unknown>):Promise<unknown>{return request('/workflow/branches/create',body)}
/** 推进已准备好的节点。 */
export function advanceNode(nodeId:string,version:number):Promise<unknown>{return request('/workflow/nodes/advance',{node_id:nodeId,expected_result_version:version})}
/** 上传附件到 AI-backend，并返回可传给 Agent 的文件标识。 */
export async function uploadFiles(files:File[]):Promise<UploadedFile[]>{const form=new FormData();files.forEach((file)=>form.append('files',file));const response=await fetch('/ai-api/file/upload',{method:'POST',body:form});const payload=await response.json() as Result<{files:UploadedFile[]}>;if(payload.code!==0)throw new Error(payload.msg||'附件上传失败');return payload.data.files}

/** 查询节点绑定 conversation_id 对应的用户可见历史消息。 */
export function getNodeConversationHistory(nodeId:string,limit=100):Promise<NodeConversationHistory>{return request('/workflow/nodes/messages/history',{node_id:nodeId,limit})}
/** 调用节点 Agent，并逐条解析 SSE 事件。 */
export async function streamNodeMessage(body:Record<string,unknown>,onEvent:(event:StreamEvent)=>void):Promise<void>{const response=await fetch('/api/workflow/nodes/messages',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${getAccessToken()}`},body:JSON.stringify({...body,stream:true})});if(!response.ok||!response.body)throw new Error(`Agent 请求失败: HTTP ${response.status}`);const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';
  /** 解析一个完整 SSE 数据块，兼容 event/data 双行和仅 data 行。 */
  const consumeBlock=(block:string):void=>{const lines=block.split(/\r?\n/).filter((line)=>line.startsWith('data:')).map((line)=>line.slice(5).trim());if(!lines.length)return;try{onEvent(JSON.parse(lines.join('\n')) as StreamEvent)}catch{onEvent({type:'model_delta',data:{content:lines.join('\n')}})}};
  while(true){const {done,value}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});const blocks=buffer.split(/\r?\n\r?\n/);buffer=blocks.pop()||'';blocks.forEach(consumeBlock);if(done)break}if(buffer.trim())consumeBlock(buffer)}
