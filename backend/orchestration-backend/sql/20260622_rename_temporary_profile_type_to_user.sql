BEGIN;

-- 将已有用户画像的类型值从 temporary 迁移为更直观的 user。
UPDATE job_market_profiles
SET profile_type = 'user'
WHERE profile_type = 'temporary';

-- 同步更新字段注释，明确画像类型表示画像的生成来源。
COMMENT ON COLUMN job_market_profiles.profile_type IS
'画像类型：system=平台系统画像，user=用户生成画像。';

COMMENT ON COLUMN job_market_profiles.user_id IS
'用户 ID；系统画像为空，用户生成画像记录所属用户。';

COMMIT;
