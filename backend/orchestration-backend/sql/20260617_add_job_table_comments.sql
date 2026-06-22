-- 为岗位业务当前保留的 4 张表补充 PostgreSQL 表注释和字段注释。
-- 说明：
-- 1. 本脚本只添加 COMMENT，不修改表结构，也不会影响已有数据。
-- 2. 字段注释使用辅助函数做存在性判断，避免不同开发阶段的字段差异导致脚本中断。
-- 3. 当前岗位业务主链路为：原始岗位数据 -> Agent 聚合分析 -> 岗位画像展示。

CREATE OR REPLACE FUNCTION pg_temp.comment_column_if_exists(
    p_table_name TEXT,
    p_column_name TEXT,
    p_comment TEXT
) RETURNS VOID AS $$
BEGIN
    -- 只有字段真实存在时才执行 COMMENT，方便脚本在不同环境重复执行。
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = p_table_name
          AND column_name = p_column_name
    ) THEN
        EXECUTE format(
            'COMMENT ON COLUMN %I.%I IS %L',
            p_table_name,
            p_column_name,
            p_comment
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- spider_crawl_runs：爬虫任务记录表
-- ---------------------------------------------------------------------

COMMENT ON TABLE spider_crawl_runs IS
'爬虫任务记录表：记录每一次招聘平台采集任务的请求参数、运行状态、采集数量和失败原因。';

SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'id', '主键 ID。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'platform', '招聘平台标识，例如 qcwy、boss、liepin。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'keyword', '本次采集使用的岗位关键词；多个关键词可用逗号拼接。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'city', '本次采集使用的城市名称或城市编码；多个城市可用逗号拼接。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'pages', '本次采集页数。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'status', '任务状态，例如 running、success、failed。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'total_count', '本次任务采集到的原始岗位数量。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'request_params', '本次采集请求参数快照，使用 JSONB 保存。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'error_message', '任务失败时的错误信息；成功时为空。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'started_at', '任务开始时间。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'finished_at', '任务结束时间。');
SELECT pg_temp.comment_column_if_exists('spider_crawl_runs', 'created_at', '记录创建时间。');

-- ---------------------------------------------------------------------
-- job_raw_records：原始岗位数据表
-- ---------------------------------------------------------------------

COMMENT ON TABLE job_raw_records IS
'原始岗位数据表：保存招聘平台采集到的岗位原始信息，是岗位画像生成的数据来源，不作为前端主展示对象。';

SELECT pg_temp.comment_column_if_exists('job_raw_records', 'id', '主键 ID。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'crawl_run_id', '关联的爬虫任务 ID，对应 spider_crawl_runs.id。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'platform', '招聘平台标识，例如 qcwy、boss、liepin。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'platform_job_id', '招聘平台侧的岗位 ID，用于辅助去重和追踪来源。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'source_url', '岗位详情页或来源页面 URL。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'raw_title', '招聘平台原始岗位标题。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'raw_company_name', '招聘平台原始公司名称。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'raw_city', '招聘平台原始城市信息。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'job_description', '招聘正文或岗位 JD，是岗位画像生成最重要的文本来源。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'raw_json', '招聘平台返回的完整原始结构，使用 JSONB 保存，方便后续重新解析。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'content_hash', '原始岗位内容哈希，用于重复采集时辅助去重。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'collected_at', '岗位数据采集时间。');
SELECT pg_temp.comment_column_if_exists('job_raw_records', 'created_at', '记录创建时间。');

-- ---------------------------------------------------------------------
-- job_directions：岗位方向字典表
-- ---------------------------------------------------------------------

COMMENT ON TABLE job_directions IS
'岗位方向字典表：保存平台定义的岗位方向，例如 AI应用开发、测试工程师、Java后端开发。';

SELECT pg_temp.comment_column_if_exists('job_directions', 'id', '主键 ID。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'name', '岗位方向名称，例如 AI应用开发。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'code', '岗位方向编码，可用于系统内部稳定标识。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'description', '岗位方向说明。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'parent_id', '父级岗位方向 ID，用于构建岗位方向层级。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'status', '岗位方向状态，例如 active、disabled。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'created_at', '记录创建时间。');
SELECT pg_temp.comment_column_if_exists('job_directions', 'updated_at', '记录更新时间。');

-- ---------------------------------------------------------------------
-- job_market_profiles：岗位画像表
-- ---------------------------------------------------------------------

COMMENT ON TABLE job_market_profiles IS
'岗位画像表：保存某个岗位方向的聚合画像，是前端页面展示的核心岗位信息。';

SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'id', '主键 ID。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'user_id', '用户 ID；系统画像为空，用户临时画像记录所属用户。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'profile_type', '画像类型：system=平台正式画像，temporary=用户临时画像。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'job_name', '岗位画像名称，由 Agent 根据输入的岗位信息提炼。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'job_overview', '岗位概述，由多个原始招聘岗位聚合生成。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'responsibilities', '岗位职责列表，使用 JSONB 保存结构化内容。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'required_skills', '必备技能要求列表，使用 JSONB 保存结构化内容。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'preferred_skills', '加分技能或优先条件列表，使用 JSONB 保存结构化内容。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'education_requirement', '学历要求总结。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'experience_requirement', '工作经验要求总结。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'certificate_requirement', '证书要求总结。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'created_at', '记录创建时间。');
SELECT pg_temp.comment_column_if_exists('job_market_profiles', 'updated_at', '记录更新时间。');
