BEGIN;

-- 历史版本会把项目 ID、节点 ID 和随机串拼接为 thread_id，长度可能超过
-- AI-backend 的会话 ID 上限。每个节点只需要一个独立 UUID 即可实现 Checkpoint 隔离。
UPDATE hai_agent.workflow_nodes
SET agent_thread_id = gen_random_uuid()::VARCHAR
WHERE agent_thread_id IS NOT NULL
  AND LENGTH(agent_thread_id) > 100;


ALTER TABLE hai_agent.workflow_nodes
ALTER COLUMN agent_thread_id TYPE VARCHAR(36);

COMMIT;
