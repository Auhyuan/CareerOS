-- 岗位画像第一版不依赖岗位方向字典。
-- 删除基于 direction_id 的索引和外键字段，画像名称及其他业务内容由 Agent 根据输入材料提炼。

BEGIN;

DROP INDEX IF EXISTS uq_job_market_profiles_system_direction;
DROP INDEX IF EXISTS uq_job_market_profiles_direction_id;

ALTER TABLE job_market_profiles
DROP COLUMN IF EXISTS direction_id;

COMMIT;
