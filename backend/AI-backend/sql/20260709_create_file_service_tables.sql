-- 文件服务：上传文件记录表
-- 执行位置：career_ai 数据库

CREATE SCHEMA IF NOT EXISTS agent;

CREATE TABLE IF NOT EXISTS agent.uploaded_files (
    file_id VARCHAR(100) PRIMARY KEY,
    original_name VARCHAR(500) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,

    extension VARCHAR(50) NOT NULL DEFAULT '',
    mime_type VARCHAR(255),
    size_bytes BIGINT NOT NULL DEFAULT 0,

    status VARCHAR(30) NOT NULL DEFAULT 'uploaded',
    parse_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    parse_error TEXT,
    parsed_text TEXT,

    metadata JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_original_name
ON agent.uploaded_files(original_name);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_parse_status
ON agent.uploaded_files(parse_status);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_created_at
ON agent.uploaded_files(created_at);

COMMENT ON TABLE agent.uploaded_files IS 'AI-backend 文件服务上传文件记录表';
COMMENT ON COLUMN agent.uploaded_files.file_id IS '文件ID，上传后返回给前端和Agent使用';
COMMENT ON COLUMN agent.uploaded_files.original_name IS '用户上传时的原始文件名';
COMMENT ON COLUMN agent.uploaded_files.stored_name IS '服务端存储文件名，通常为file_id加扩展名';
COMMENT ON COLUMN agent.uploaded_files.storage_path IS '服务端本地磁盘存储路径';
COMMENT ON COLUMN agent.uploaded_files.extension IS '文件扩展名，例如.pdf、.txt、.md';
COMMENT ON COLUMN agent.uploaded_files.mime_type IS '上传文件MIME类型';
COMMENT ON COLUMN agent.uploaded_files.size_bytes IS '文件大小，单位字节';
COMMENT ON COLUMN agent.uploaded_files.status IS '文件状态：uploaded=已上传，deleted=已删除等';
COMMENT ON COLUMN agent.uploaded_files.parse_status IS '解析状态：pending=未解析，success=解析成功，failed=解析失败';
COMMENT ON COLUMN agent.uploaded_files.parse_error IS '最近一次解析失败原因';
COMMENT ON COLUMN agent.uploaded_files.parsed_text IS '解析后的文本内容缓存';
COMMENT ON COLUMN agent.uploaded_files.metadata IS '扩展元数据';
COMMENT ON COLUMN agent.uploaded_files.created_at IS '创建时间';
COMMENT ON COLUMN agent.uploaded_files.updated_at IS '更新时间';
