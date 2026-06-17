# API-SPEC - 鎺ュ彛鏂囨。

## 1. 閫氱敤绾﹀畾

### 1.1 鍩虹鍦板潃

鏈湴榛樿锛?
```text
鑳藉姏灞?capability-backend: http://127.0.0.1:8090
缂栨帓灞?orchestration-backend: http://127.0.0.1:8091
```

鍚姩鏂瑰紡锛?
```powershell
cd backend
python app/main.py
```

### 1.2 缁熶竴鍝嶅簲

鎵€鏈変笟鍔℃帴鍙ｇ粺涓€杩斿洖锛?
```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

### 1.3 鏉冮檺璇存槑

Python 鏈嶅姟涓嶅仛鐧诲綍鍜屾潈闄愭帶鍒躲€傝皟鐢ㄦ柟闇€瑕佸湪 Java 灞傚畬鎴愭潈闄愬垽鏂悗锛屽啀璋冪敤 Python 鎺ュ彛銆?
## 2. Agent 鎺ュ彛

### 2.1 Agent 鍋ュ悍妫€鏌?
```http
GET /agent/health
```

鍝嶅簲锛?
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "service": "agent",
    "status": "ok"
  }
}
```

### 2.2 鏌ヨ妯″瀷閰嶇疆

```http
GET /agent/model/config
```

璇存槑锛氳繑鍥炶劚鏁忓悗鐨勬ā鍨嬮厤缃紝鍙敤浜庣幆澧冩鏌ャ€?
鍝嶅簲 data锛?
```json
{
  "provider": "openai-compatible",
  "base_url": "https://api.example.com/v1",
  "chat_model": "xxx-chat",
  "embedding_model": "xxx-embedding",
  "rerank_model": null,
  "langsmith_tracing": false,
  "langsmith_endpoint": "https://api.smith.langchain.com",
  "langsmith_project": "career-ai",
  "has_api_key": true,
  "has_langsmith_api_key": false
}
```

### 2.3 鏌ヨ Agent 鑳藉姏

```http
GET /agent/capabilities
```

鍝嶅簲 data锛?
```json
{
  "service_name": "agent",
  "modules": ["agent", "model", "schemas", "prompts", "tools"],
  "enabled_features": ["openai_compatible_chat_model", "postgres_checkpointer"]
}
```

### 2.4 杩愯閫氱敤 Agent

```http
POST /agent/run
```

璇锋眰锛?
```json
{
  "query": "璇锋€荤粨杩欎簺宀椾綅鐨勬妧鑳借姹?,
  "conversation_id": "career-profile-ai-app-dev",
  "system_prompt": "浣犳槸灏变笟鎸囧骞冲彴鐨勫矖浣嶅垎鏋愪笓瀹躲€?,
  "inputs": {
    "job_direction": "AI搴旂敤寮€鍙?,
    "job_samples": []
  },
  "files": [],
  "tools": [],
  "optional_features": {
    "long_term_memory_enabled": false,
    "conversation_context_enabled": true,
    "checkpoint_enabled": true,
    "deferred_tool_filter_enabled": false
  },
  "runtime_options": {
    "model": null,
    "temperature": 0.2,
    "timeout_seconds": 60,
    "max_retries": 2
  }
}
```

瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 |
| --- | --- | --- | --- |
| `query` | string | 鏄?| 鏈浠诲姟鎸囦护銆?|
| `conversation_id` | string | 鍚?| 浼氳瘽 ID锛涗笉浼犳椂鏈嶅姟绔敓鎴愩€?|
| `system_prompt` | string | 鍚?| 鏈杩愯浣跨敤鐨勭郴缁熸彁绀鸿瘝銆?|
| `inputs` | object | 鍚?| 缂栨帓灞傛敞鍏ョ殑涓氬姟鍙橀噺銆?|
| `files` | array | 鍚?| 闄勪欢涓婁笅鏂囷紝褰撳墠棰勭暀銆?|
| `tools` | array | 鍚?| 鏈鍏佽浣跨敤鐨勫伐鍏峰悕銆?|
| `optional_features` | object | 鍚?| 鍙€夎兘鍔涘紑鍏炽€?|
| `runtime_options` | object | 鍚?| 妯″瀷杩愯鍙傛暟銆?|

鍝嶅簲 data锛?
```json
{
  "answer": "妯″瀷鍥炲鍐呭",
  "structured_output": {}
}
```

娉ㄦ剰锛?
- `/agent/run` 涓嶆帴鏀?`agent_id`銆?- `/agent/run` 涓嶆帴鏀跺閮?`input_messages`銆?- 鍘嗗彶浼氳瘽鐢?`conversation_id` 浠?ContextService 鑾峰彇銆?- Checkpoint 鐢ㄤ簬 LangGraph 鐘舵€佹寔涔呭寲锛屼笉浣滀负璺ㄨ疆鍘嗗彶鏉ユ簮銆?
## 3. Agent 浼氳瘽鎺ュ彛

### 3.1 鏌ヨ浼氳瘽

```http
POST /agent/conversations/search
```

璇锋眰锛?
```json
{
  "conversation_id": "career-profile-ai-app-dev"
}
```

鍝嶅簲 data锛?
```json
{
  "total": 1,
  "items": [
    {
      "conversation_id": "career-profile-ai-app-dev",
      "title": "AI搴旂敤寮€鍙戝矖浣嶇敾鍍?,
      "status": "active",
      "metadata": {},
      "created_at": "2026-06-17T10:00:00+08:00",
      "updated_at": "2026-06-17T10:00:00+08:00"
    }
  ]
}
```

### 3.2 鏌ヨ浼氳瘽娑堟伅

```http
POST /agent/conversations/messages
```

璇锋眰锛?
```json
{
  "conversation_id": "career-profile-ai-app-dev",
  "limit": 50
}
```

鍝嶅簲 data锛?
```json
{
  "conversation_id": "career-profile-ai-app-dev",
  "messages": [
    {
      "message_id": "msg_xxx",
      "role": "user",
      "message_type": "user_message",
      "content": "璇风敓鎴?AI 搴旂敤寮€鍙戝矖浣嶇敾鍍?,
      "structured_content": null,
      "tool_name": null,
      "tool_call_id": null,
      "status": "success",
      "error_message": null,
      "metadata": {}
    }
  ]
}
```

## 4. Agent 妯℃澘鎺ュ彛

### 4.1 鍒涘缓鎴栨洿鏂版ā鏉?
```http
POST /agent/templates/upsert
```

璇锋眰锛?
```json
{
  "agent_id": "job-profile-agent",
  "agent_name": "宀椾綅鐢诲儚鍒嗘瀽 Agent",
  "description": "鐢ㄤ簬鏍规嵁鎷涜仒鏁版嵁鐢熸垚宀椾綅鐢诲儚",
  "config": {
    "system_prompt": "浣犳槸灏变笟鎸囧骞冲彴鐨勫矖浣嶅垎鏋愪笓瀹躲€?,
    "tools": [],
    "runtime_options": {
      "temperature": 0.2
    }
  },
  "status": "active"
}
```

### 4.2 鏌ヨ妯℃澘璇︽儏

```http
POST /agent/templates/detail
```

璇锋眰锛?
```json
{
  "agent_id": "job-profile-agent"
}
```

### 4.3 鏌ヨ妯℃澘鍒楄〃

```http
POST /agent/templates/search
```

璇锋眰锛?
```json
{
  "keyword": "宀椾綅鐢诲儚",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

鍝嶅簲 data锛?
```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": []
}
```

## 5. 鐖櫕鎺ュ彛

### 5.1 鐖櫕鍋ュ悍妫€鏌?
```http
GET /spider/health
```

### 5.2 閲囬泦鍓嶇▼鏃犲咖宀椾綅

```http
POST /spider/qcwy/jobs
```

璇存槑锛氳鎺ュ彛灞炰簬鑳藉姏灞傦紝鍙礋璐ｉ噰闆嗗苟杩斿洖宀椾綅鏁版嵁锛屼笉璐熻矗鍏ュ簱銆?
璇锋眰锛?
```json
{
  "keywords": ["AI搴旂敤寮€鍙?],
  "cities": ["娣卞湷"],
  "pages": 1,
  "page_size": 20,
  "fetch_mode": "browser",
  "fields": [],
  "save_raw_json": false,
  "save_csv": false,
  "save_excel": false,
  "browser_headless": false,
  "browser_executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "browser_wait_seconds": 25
}
```

瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
| --- | --- | --- |
| `keywords` | string[] | 宀椾綅鍏抽敭璇嶅垪琛ㄣ€?|
| `cities` | string[] | 鍩庡競鍚嶇О鎴栧煄甯傜紪鐮佸垪琛ㄣ€?|
| `pages` | number | 姣忎釜鍏抽敭璇嶅拰鍩庡競缁勫悎閲囬泦椤垫暟銆?|
| `page_size` | number | 姣忛〉宀椾綅鏁伴噺銆?|
| `fetch_mode` | string | `browser` 鎴?`requests`銆?|
| `fields` | string[] | 杩斿洖瀛楁鍒楄〃锛涚┖鏁扮粍杩斿洖鍏ㄩ儴瀛楁銆?|
| `save_raw_json` | boolean | 鏄惁淇濆瓨鍘熷 JSON 鏂囦欢銆?|
| `save_csv` | boolean | 鏄惁淇濆瓨 CSV銆?|
| `save_excel` | boolean | 鏄惁淇濆瓨 Excel銆?|
| `browser_headless` | boolean | 娴忚鍣ㄦ槸鍚︽棤澶磋繍琛屻€?|
| `browser_executable_path` | string | 鏈満娴忚鍣ㄨ矾寰勩€?|
| `browser_wait_seconds` | number | 绛夊緟宀椾綅鎺ュ彛鍝嶅簲鐨勭鏁般€?|

鍝嶅簲 data锛?
```json
{
  "platform": "qcwy",
  "total": 20,
  "rows": [],
  "csv_path": null,
  "excel_path": null
}
```

## 6. 宀椾綅鎺ュ彛

### 6.1 宀椾綅鏈嶅姟鍋ュ悍妫€鏌?
```http
GET /job/health
```

### 6.2 閲囬泦骞跺叆搴撳墠绋嬫棤蹇у矖浣?
```http
POST /job/crawl/qcwy/jobs
```

璇存槑锛氳鎺ュ彛灞炰簬缂栨帓灞傘€傚畠鍏堣皟鐢ㄨ兘鍔涘眰 `/spider/qcwy/jobs` 鑾峰彇瀹屾暣宀椾綅鏁版嵁锛屽啀鐢辩紪鎺掑眰鍐欏叆 `spider_crawl_runs`銆乣job_raw_records`銆乣job_raw_records`銆?
璇锋眰锛?
```json
{
  "keywords": ["AI搴旂敤寮€鍙?],
  "cities": ["娣卞湷"],
  "pages": 1,
  "page_size": 20,
  "fetch_mode": "browser",
  "fields": [],
  "save_raw_json": false,
  "save_csv": false,
  "save_excel": false,
  "persist_to_db": true,
  "browser_headless": false,
  "browser_executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "browser_wait_seconds": 25
}
```

鍝嶅簲 data锛?
```json
{
  "platform": "qcwy",
  "total": 20,
  "rows": [],
  "csv_path": null,
  "excel_path": null,
  "crawl_run_id": 1,
  "ingest_stats": {
    "raw_created": 20
  }
}
```

### 6.3 鏌ヨ宀椾綅鏂瑰悜鍒楄〃

```http
POST /job/directions/search
```

璇锋眰锛?
```json
{
  "keyword": "AI",
  "status": "active",
  "page": 1,
  "page_size": 20
}
```

### 6.4 鏌ヨ宀椾綅鏂瑰悜璇︽儏

```http
GET /job/directions/{direction_id}
```

### 6.5 鏌ヨ宀椾綅鏂瑰悜鐢诲儚

```http
GET /job/directions/{direction_id}/profile
```

鍝嶅簲 data锛?
```json
{
  "id": 1,
  "direction_id": 1,
  "job_name": "AI搴旂敤寮€鍙?,
  "job_overview": "宀椾綅姒傝堪",
  "responsibilities": [],
  "required_skills": [],
  "preferred_skills": [],
  "education_requirement": "鏈鍙婁互涓?,
  "experience_requirement": "1-3骞?,
  "certificate_requirement": "鏃犲己鍒惰瘉涔﹁姹?,
  "source_job_ids": [],
  "source_filters": {},
  "model_name": "xxx-chat",
  "analysis_version": "v1",
  "created_at": "2026-06-17T10:00:00+08:00",
  "updated_at": "2026-06-17T10:00:00+08:00"
}
```

### 6.6 查询原始岗位列表

```http
POST /job/raw-records/search
```

璇锋眰锛?
```json
{
  "keyword": "AI搴旂敤寮€鍙?,
  "city": "娣卞湷",
  "platform": "qcwy",
  "page": 1,
  "page_size": 20
}
```

### 6.7 查询原始岗位详情

```http
GET /job/raw-records/{raw_record_id}
```

## 7. 缂栨帓灞傛帴鍙ｈ鍒?
浠ヤ笅鎺ュ彛灞炰簬寤鸿鏂板鐨勭紪鎺掑眰锛屼笉寤鸿鏀惧叆 Agent 鑳藉姏灞傘€?
### 7.1 鐢熸垚宀椾綅鐢诲儚

```http
POST /job/profiles/generate
```

璇锋眰鑽夋锛?
```json
{
  "direction_id": 1,
  "keyword": "AI搴旂敤寮€鍙?,
  "city": "娣卞湷",
  "sample_limit": 50,
  "agent_template_id": "job-profile-agent",
  "save_profile": true
}
```

鍝嶅簲鑽夋锛?
```json
{
  "status": "planned",
  "message": "宀椾綅鐢诲儚鐢熸垚娴佺▼灏氭湭瀹炵幇锛屽綋鍓嶆帴鍙ｄ粎浣滀负 API 鍒嗗潡鍗犱綅銆?
}
```

### 7.2 閲嶆柊鐢熸垚宀椾綅鐢诲儚

```http
POST /job/profiles/regenerate
```

### 7.3 鏌ヨ宀椾綅鐢诲儚鐢熸垚浠诲姟

```http
POST /job/profiles/tasks/search
```


