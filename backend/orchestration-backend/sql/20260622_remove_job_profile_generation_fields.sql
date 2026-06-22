-- 从岗位画像表中删除生成过程相关字段。
-- 岗位画像表只保存前端需要展示的岗位画像内容；
-- 模型、分析版本、来源岗位和筛选条件后续如需追踪，应放入独立的画像生成任务表。

ALTER TABLE job_market_profiles
    DROP COLUMN IF EXISTS source_job_ids,
    DROP COLUMN IF EXISTS source_filters,
    DROP COLUMN IF EXISTS model_name,
    DROP COLUMN IF EXISTS analysis_version;
