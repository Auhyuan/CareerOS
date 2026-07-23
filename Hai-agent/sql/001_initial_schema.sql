BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS hai_agent;

CREATE TABLE hai_agent.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    password_hash TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_hai_users_username_lower ON hai_agent.users (LOWER(username));
CREATE UNIQUE INDEX uq_hai_users_email_lower ON hai_agent.users (LOWER(email)) WHERE email IS NOT NULL;

COMMENT ON TABLE hai_agent.users IS 'Hai-agent 本地登录用户表';
COMMENT ON COLUMN hai_agent.users.user_id IS '用户唯一 ID，同时作为业务数据隔离标识';
COMMENT ON COLUMN hai_agent.users.username IS '登录用户名，不区分大小写且唯一';
COMMENT ON COLUMN hai_agent.users.email IS '用户邮箱，不区分大小写且唯一，可为空';
COMMENT ON COLUMN hai_agent.users.password_hash IS 'Argon2 密码哈希，不保存明文密码';
COMMENT ON COLUMN hai_agent.users.status IS '用户状态：active、disabled';
COMMENT ON COLUMN hai_agent.users.created_at IS '创建时间';
COMMENT ON COLUMN hai_agent.users.updated_at IS '更新时间';
COMMENT ON COLUMN hai_agent.users.last_login_at IS '最后一次登录成功时间';

CREATE TABLE hai_agent.auth_refresh_tokens (
    token_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES hai_agent.users(user_id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hai_refresh_tokens_user ON hai_agent.auth_refresh_tokens(user_id, created_at DESC);
CREATE INDEX idx_hai_refresh_tokens_active ON hai_agent.auth_refresh_tokens(expires_at) WHERE revoked_at IS NULL;

COMMENT ON TABLE hai_agent.auth_refresh_tokens IS 'JWT Refresh Token 生命周期记录';
COMMENT ON COLUMN hai_agent.auth_refresh_tokens.token_id IS 'Refresh Token 的 JWT jti';
COMMENT ON COLUMN hai_agent.auth_refresh_tokens.user_id IS '令牌所属用户';
COMMENT ON COLUMN hai_agent.auth_refresh_tokens.token_hash IS 'Refresh Token 的 SHA-256 摘要';
COMMENT ON COLUMN hai_agent.auth_refresh_tokens.expires_at IS '令牌过期时间';
COMMENT ON COLUMN hai_agent.auth_refresh_tokens.revoked_at IS '令牌撤销时间，非空表示已失效';
COMMENT ON COLUMN hai_agent.auth_refresh_tokens.created_at IS '令牌签发时间';

CREATE TABLE hai_agent.projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES hai_agent.users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    brand_name VARCHAR(255),
    event_type VARCHAR(100),
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    current_stage VARCHAR(50) NOT NULL DEFAULT 'project_preparation',
    current_branch_id UUID,
    current_node_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_hai_projects_user_updated ON hai_agent.projects(user_id, updated_at DESC);
CREATE INDEX idx_hai_projects_status_updated ON hai_agent.projects(status, updated_at DESC);

COMMENT ON TABLE hai_agent.projects IS '活动策划项目聚合根';
COMMENT ON COLUMN hai_agent.projects.project_id IS '项目唯一 ID';
COMMENT ON COLUMN hai_agent.projects.user_id IS '项目所属用户，用于用户数据隔离';
COMMENT ON COLUMN hai_agent.projects.name IS '项目名称';
COMMENT ON COLUMN hai_agent.projects.customer_name IS '客户名称';
COMMENT ON COLUMN hai_agent.projects.brand_name IS '品牌名称';
COMMENT ON COLUMN hai_agent.projects.event_type IS '活动类型';
COMMENT ON COLUMN hai_agent.projects.description IS '项目说明';
COMMENT ON COLUMN hai_agent.projects.status IS '项目状态：active、completed、cancelled、archived';
COMMENT ON COLUMN hai_agent.projects.current_stage IS '当前业务阶段编码';
COMMENT ON COLUMN hai_agent.projects.current_branch_id IS '当前激活分支';
COMMENT ON COLUMN hai_agent.projects.current_node_id IS '用户当前正在操作的节点';
COMMENT ON COLUMN hai_agent.projects.metadata IS '项目扩展配置';
COMMENT ON COLUMN hai_agent.projects.created_at IS '创建时间';
COMMENT ON COLUMN hai_agent.projects.updated_at IS '更新时间';
COMMENT ON COLUMN hai_agent.projects.archived_at IS '归档时间';

CREATE TABLE hai_agent.workflow_branches (
    branch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES hai_agent.projects(project_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    source_branch_id UUID REFERENCES hai_agent.workflow_branches(branch_id) ON DELETE SET NULL,
    source_node_id UUID,
    head_node_id UUID,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    is_main BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_hai_workflow_branches_project ON hai_agent.workflow_branches(project_id, created_at);
CREATE UNIQUE INDEX uq_hai_workflow_branches_main
    ON hai_agent.workflow_branches(project_id)
    WHERE is_main = TRUE AND status <> 'archived';

COMMENT ON TABLE hai_agent.workflow_branches IS '项目方案演进分支';
COMMENT ON COLUMN hai_agent.workflow_branches.branch_id IS '分支唯一 ID';
COMMENT ON COLUMN hai_agent.workflow_branches.project_id IS '所属项目';
COMMENT ON COLUMN hai_agent.workflow_branches.name IS '分支名称';
COMMENT ON COLUMN hai_agent.workflow_branches.source_branch_id IS '来源分支';
COMMENT ON COLUMN hai_agent.workflow_branches.source_node_id IS '创建分支时选择的历史来源节点';
COMMENT ON COLUMN hai_agent.workflow_branches.head_node_id IS '当前分支头节点';
COMMENT ON COLUMN hai_agent.workflow_branches.status IS '分支状态：active、completed、archived';
COMMENT ON COLUMN hai_agent.workflow_branches.is_main IS '是否为项目主分支';
COMMENT ON COLUMN hai_agent.workflow_branches.created_at IS '创建时间';
COMMENT ON COLUMN hai_agent.workflow_branches.updated_at IS '更新时间';
COMMENT ON COLUMN hai_agent.workflow_branches.archived_at IS '归档时间';

CREATE TABLE hai_agent.workflow_nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES hai_agent.projects(project_id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES hai_agent.workflow_branches(branch_id) ON DELETE CASCADE,
    parent_node_id UUID REFERENCES hai_agent.workflow_nodes(node_id) ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL,
    node_type VARCHAR(60) NOT NULL DEFAULT 'stage',
    stage VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'working',
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    input_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    handoff_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_version INTEGER NOT NULL DEFAULT 0,
    agent_id VARCHAR(100),
    agent_thread_id VARCHAR(150),
    checkpoint_id VARCHAR(255),
    error_code VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_workflow_nodes_branch_sequence UNIQUE(branch_id, sequence_no),
    CONSTRAINT ck_workflow_nodes_sequence_positive CHECK(sequence_no > 0),
    CONSTRAINT ck_workflow_nodes_result_version_nonnegative CHECK(result_version >= 0)
);

CREATE UNIQUE INDEX uq_hai_workflow_nodes_agent_thread
    ON hai_agent.workflow_nodes(agent_thread_id)
    WHERE agent_thread_id IS NOT NULL;
CREATE INDEX idx_hai_workflow_nodes_project_branch
    ON hai_agent.workflow_nodes(project_id, branch_id, sequence_no);
CREATE INDEX idx_hai_workflow_nodes_parent ON hai_agent.workflow_nodes(parent_node_id);
CREATE INDEX idx_hai_workflow_nodes_status ON hai_agent.workflow_nodes(status, created_at);

COMMENT ON TABLE hai_agent.workflow_nodes IS '多阶段树状工作流节点';
COMMENT ON COLUMN hai_agent.workflow_nodes.node_id IS '节点唯一 ID';
COMMENT ON COLUMN hai_agent.workflow_nodes.project_id IS '所属项目';
COMMENT ON COLUMN hai_agent.workflow_nodes.branch_id IS '所属分支';
COMMENT ON COLUMN hai_agent.workflow_nodes.parent_node_id IS '父节点；系统不保存 next_node_id，子节点通过本字段反向查询';
COMMENT ON COLUMN hai_agent.workflow_nodes.sequence_no IS '分支内展示序号，不作为父子关系依据';
COMMENT ON COLUMN hai_agent.workflow_nodes.node_type IS '节点业务类型';
COMMENT ON COLUMN hai_agent.workflow_nodes.stage IS '节点阶段编码';
COMMENT ON COLUMN hai_agent.workflow_nodes.status IS '节点状态：working、ready、completed、failed、cancelled';
COMMENT ON COLUMN hai_agent.workflow_nodes.title IS '节点展示标题';
COMMENT ON COLUMN hai_agent.workflow_nodes.summary IS '当前阶段结果摘要';
COMMENT ON COLUMN hai_agent.workflow_nodes.input_context IS '节点启动时接收的交接上下文';
COMMENT ON COLUMN hai_agent.workflow_nodes.result_data IS 'Agent 保存的当前阶段最新 JSON 结果';
COMMENT ON COLUMN hai_agent.workflow_nodes.handoff_context IS '节点完成后交给后续节点的累计业务状态';
COMMENT ON COLUMN hai_agent.workflow_nodes.result_version IS '结果版本号，用于乐观锁和推进校验';
COMMENT ON COLUMN hai_agent.workflow_nodes.agent_id IS 'AI-backend Agent 模板 ID';
COMMENT ON COLUMN hai_agent.workflow_nodes.agent_thread_id IS '当前步骤节点独立的 LangGraph thread_id';
COMMENT ON COLUMN hai_agent.workflow_nodes.checkpoint_id IS 'LangGraph Checkpoint ID，仅用于运行排查';
COMMENT ON COLUMN hai_agent.workflow_nodes.error_code IS '节点失败错误码';
COMMENT ON COLUMN hai_agent.workflow_nodes.error_message IS '节点失败错误信息';
COMMENT ON COLUMN hai_agent.workflow_nodes.started_at IS '节点开始执行时间';
COMMENT ON COLUMN hai_agent.workflow_nodes.completed_at IS '节点完成时间';
COMMENT ON COLUMN hai_agent.workflow_nodes.result_updated_at IS '阶段结果最后更新时间';
COMMENT ON COLUMN hai_agent.workflow_nodes.created_at IS '节点创建时间';

ALTER TABLE hai_agent.projects
    ADD CONSTRAINT fk_hai_projects_current_branch
    FOREIGN KEY(current_branch_id) REFERENCES hai_agent.workflow_branches(branch_id) ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE hai_agent.projects
    ADD CONSTRAINT fk_hai_projects_current_node
    FOREIGN KEY(current_node_id) REFERENCES hai_agent.workflow_nodes(node_id) ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE hai_agent.workflow_branches
    ADD CONSTRAINT fk_hai_workflow_branches_source_node
    FOREIGN KEY(source_node_id) REFERENCES hai_agent.workflow_nodes(node_id) ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE hai_agent.workflow_branches
    ADD CONSTRAINT fk_hai_workflow_branches_head_node
    FOREIGN KEY(head_node_id) REFERENCES hai_agent.workflow_nodes(node_id) ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

COMMIT;
