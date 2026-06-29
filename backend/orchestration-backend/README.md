# orchestration-backend

`orchestration-backend` 鏄氨涓氭寚瀵?AI 骞冲彴鐨勪笟鍔＄紪鎺掑眰锛岃礋璐ｆ妸鑳藉姏灞傛彁渚涚殑 Agent銆佺埇铏瓑鑳藉姏缁勫悎鎴愬氨涓氬钩鍙颁笟鍔℃祦绋嬨€?

## 鑱岃矗杈圭晫

缂栨帓灞傚彲浠ヨ鍐欏矖浣嶄笟鍔¤〃锛屽苟閫氳繃 HTTP API 璋冪敤 `AI-backend`銆?

褰撳墠妯″潡锛?

```text
app/server/job/        # 宀椾綅涓氬姟缂栨帓
app/common/            # 閫氱敤閰嶇疆銆佹暟鎹簱銆佸搷搴斻€佸紓甯稿鐞?
sql/                   # 缂栨帓灞傛暟鎹簱鑴氭湰
```

## 涓昏鎺ュ彛

宀椾綅閲囬泦锛?

```text
GET  /job/health
POST /job/crawl/qcwy/jobs
```

鍘熷宀椾綅锛?

```text
POST /job/raw-records/search
GET  /job/raw-records/{raw_record_id}
```

宀椾綅鏂瑰悜锛?

```text
POST /job/directions/search
GET  /job/directions/{direction_id}
```

宀椾綅鐢诲儚锛?

```text
GET  /job/profiles/{profile_id}
POST /job/profiles/generate
POST /job/skills/search
POST /job/skills/create
```

鐢ㄦ埛宀椾綅鐢诲儚鐢熸垚璇锋眰锛?

```json
{
  "profile_type": "user",
  "agent_id": "job-profile-agent",
  "user_id": "10001",
  "job_text": "鐢ㄦ埛鎻愪氦鐨勫矖浣嶇浉鍏虫枃鏈?,
  "use_system_job_data": false
}
```

`/job/profiles/generate` 鏄粺涓€鐢熸垚鍏ュ彛锛?

- `profile_type=user`锛氭墽琛岀敤鎴峰矖浣嶇敾鍍忕敓鎴愭祦绋嬨€?
- `profile_type=system`锛氱郴缁熺敾鍍忚矾绾块鐣欙紝褰撳墠鏆傛湭寮€鏀俱€?

鐢ㄦ埛鐢诲儚娴佺▼浼氳皟鐢ㄨ兘鍔涘眰 `/agent/run` 鑾峰彇缁撴瀯鍖栫敾鍍忥紝鏍￠獙閫氳繃鍚庡啓鍏?
`job_market_profiles`銆?

## 鏁版嵁搴?

缂栨帓灞傚綋鍓嶄娇鐢?`public` schema 鐨勫矖浣嶄笟鍔¤〃锛?

```text
spider_crawl_runs
job_raw_records
job_directions
job_market_profiles
```

SQL 鑴氭湰鏀惧湪锛?

```text
backend/orchestration-backend/sql
```

## 鍚姩

```powershell
cd D:\study\get_job_data\backend\orchestration-backend
pip install -r requirements.txt
python app/main.py
```

榛樿鍦板潃锛?

```text
http://127.0.0.1:8091
```

## 鐜鍙橀噺

閰嶇疆鏂囦欢锛?

```text
.env
.env.example
```

甯歌閰嶇疆锛?

```text
FASTAPI_HOST
FASTAPI_PORT
AI_BACKEND_BASE_URL
AI_BACKEND_TIMEOUT_SECONDS
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DATABASE
```

