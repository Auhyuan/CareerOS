export interface Result<T>{code:number;msg:string;data:T}
export interface User{user_id:string;username:string;email:string|null;status:string}
export interface TokenPair{access_token:string;refresh_token:string;token_type:string;expires_in:number;user:User}
export interface Project{project_id:string;name:string;customer_name:string|null;brand_name:string|null;event_type:string|null;description:string|null;status:string;current_stage:string;current_branch_id:string|null;current_node_id:string|null;metadata:Record<string,unknown>;created_at:string;updated_at:string}
export interface WorkflowBranch{branch_id:string;name:string;source_branch_id:string|null;source_node_id:string|null;head_node_id:string|null;status:string;is_main:boolean;created_at:string}
export interface WorkflowNode{node_id:string;branch_id:string;parent_node_id:string|null;sequence_no:number;stage_code:string;status:string;title:string;summary:string|null;input_context:Record<string,unknown>;result_data:Record<string,unknown>;handoff_context:Record<string,unknown>;result_version:number;agent_id:string|null;agent_thread_id:string|null;created_at:string;completed_at:string|null}
export interface ProjectDetail{project:Project;branches:WorkflowBranch[];nodes:WorkflowNode[]}
export interface ProjectList{items:Project[];total:number;page:number;page_size:number}
export interface UploadedFile{file_id:string;original_name:string;extension:string;size_bytes:number;conversion_status?:string}
export interface TimelineItem{id:string;kind:'user'|'reasoning'|'answer'|'tool'|'status'|'error';title?:string;content:string;detail?:unknown;state?:'running'|'done'|'error'}
export interface StreamEvent{type:string;data?:Record<string,unknown>}

export interface ConversationMessage{message_id:string;role:string;message_type:string;content:string|null;structured_content:Record<string,unknown>|null;tool_name:string|null;status:string;error_message:string|null}
export interface NodeConversationHistory{node_id:string;conversation_id:string;messages:ConversationMessage[]}
