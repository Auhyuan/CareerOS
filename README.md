# 灏变笟鎸囧 AI 骞冲彴鍚庣

杩欐槸涓€涓潰鍚戝氨涓氭寚瀵?AI 骞冲彴鐨?Python 鍚庣椤圭洰銆傚綋鍓嶅悗绔凡缁忔媶鎴愪袱涓嫭绔?FastAPI 鏈嶅姟锛?
- `capability-backend`锛氳兘鍔涘眰鏈嶅姟锛屾彁渚涢€氱敤 AI 鍜屾暟鎹噰闆嗚兘鍔涖€?- `orchestration-backend`锛氱紪鎺掑眰鏈嶅姟锛屾彁渚涘拰灏变笟涓氬姟寮虹浉鍏崇殑娴佺▼缂栨帓涓庢暟鎹叆搴撹兘鍔涖€?
Java 鍚庣鍚庣画璐熻矗鐧诲綍銆佹潈闄愩€佺敤鎴枫€佺粍缁囥€侀〉闈㈡祦绋嬪拰缁熶竴璋冪敤鍏ュ彛锛汸ython 鍚庣鍙礋璐?AI 鑳藉姏銆佺埇铏兘鍔涖€佸矖浣嶆暟鎹鐞嗗拰涓氬姟鏅鸿兘缂栨帓銆?
## 鐩綍缁撴瀯

```text
get_job_data/
  backend/
    capability-backend/
      app/
        main.py
        server/
          agent/
          spider/
      requirements.txt
      .env.example

    orchestration-backend/
      app/
        main.py
        server/
          job/
      requirements.txt
      .env.example

  docs/
    鏋舵瀯鍥?md
    AC-楠屾敹鏍囧噯鏂囨。.md
    TDD-鎶€鏈爣鍑嗘枃妗?md
    ERD-鏁版嵁搴撹璁?md
    API-SPEC鎺ュ彛鏂囨。.md
```

## 鏈嶅姟杈圭晫

### capability-backend

鑳藉姏灞傚彧璐熻矗閫氱敤鑳藉姏锛屼笉鐩存帴鍐欎笟鍔″簱銆?
褰撳墠鍖呭惈锛?
- Agent 鑳藉姏锛歚/agent/*`
- 鐖櫕鑳藉姏锛歚/spider/*`

鍏稿瀷鎺ュ彛锛?
```text
GET  /agent/health
POST /agent/run
GET  /spider/health
POST /spider/qcwy/jobs
```

娉ㄦ剰锛歚/spider/qcwy/jobs` 鍙礋璐ｉ噰闆嗗矖浣嶆暟鎹苟杩斿洖 `rows`锛屼笉璐熻矗鍏ュ簱銆?
### orchestration-backend

缂栨帓灞傝礋璐ｅ氨涓氬钩鍙颁笟鍔℃祦绋嬪拰涓氬姟鏁版嵁鍏ュ簱銆?
褰撳墠鍖呭惈锛?
- 宀椾綅搴撴煡璇細`/job/raw-records/search`
- 宀椾綅鏂瑰悜鏌ヨ锛歚/job/directions/search`
- 宀椾綅鐢诲儚鏌ヨ锛歚/job/directions/{direction_id}/profile`
- 鍓嶇▼鏃犲咖閲囬泦骞跺叆搴擄細`/job/crawl/qcwy/jobs`

`/job/crawl/qcwy/jobs` 浼氳皟鐢ㄨ兘鍔涘眰鐨?`/spider/qcwy/jobs`锛屾嬁鍒板畬鏁村矖浣嶆暟鎹悗鍐嶅啓鍏?PostgreSQL銆?
## 璋冪敤閾捐矾

```text
Java / 鍓嶇
  -> orchestration-backend:8091 /job/crawl/qcwy/jobs
      -> capability-backend:8090 /spider/qcwy/jobs
      <- 杩斿洖宀椾綅閲囬泦 rows
      -> orchestration-backend 鍐欏叆 PostgreSQL
  <- 杩斿洖 crawl_run_id / ingest_stats / rows
```

## 鐜瑕佹眰

寤鸿浣跨敤 Conda 鍒涘缓 Python 鐜銆?
鎺ㄨ崘 Python 鐗堟湰锛?
```text
Python 3.12
```

瀹夎渚濊禆锛?
```powershell
conda activate job_spider
cd backend/capability-backend
pip install -r requirements.txt

cd backend/orchestration-backend
pip install -r requirements.txt
```

濡傛灉涓や釜鏈嶅姟渚濊禆淇濇寔涓€鑷达紝鍚庣画鍙互鑰冭檻鎶藉嚭缁熶竴渚濊禆绠＄悊鏂瑰紡銆?
## 閰嶇疆鏂囦欢

涓や釜鏈嶅姟鍚勮嚜缁存姢鑷繁鐨?`.env`銆?
鑳藉姏灞傜ず渚嬶細

```text
backend/capability-backend/.env
```

鏍稿績閰嶇疆锛?
```env
FASTAPI_HOST="127.0.0.1"
FASTAPI_PORT=8090
QCWY_BROWSER_EXECUTABLE_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"

LLM_PROVIDER="openai_compatible"
LLM_API_KEY="your_llm_api_key"
LLM_BASE_URL="https://api.deepseek.com"
LLM_MODEL="deepseek-chat"
```

缂栨帓灞傜ず渚嬶細

```text
backend/orchestration-backend/.env
```

鏍稿績閰嶇疆锛?
```env
FASTAPI_HOST="127.0.0.1"
FASTAPI_PORT=8091
CAPABILITY_BASE_URL="http://127.0.0.1:8090"
CAPABILITY_TIMEOUT_SECONDS=180

POSTGRES_HOST="127.0.0.1"
POSTGRES_PORT=5433
POSTGRES_USER="remote_root"
POSTGRES_PASSWORD="your_postgres_password"
POSTGRES_DATABASE="career_ai"
```

## 鍚姩鏈嶅姟

鍏堝惎鍔ㄨ兘鍔涘眰锛?
```powershell
conda activate job_spider
cd D:\study\get_job_data\backend\capability-backend
python app/main.py
```

榛樿鍦板潃锛?
```text
http://127.0.0.1:8090
```

鍐嶅惎鍔ㄧ紪鎺掑眰锛?
```powershell
conda activate job_spider
cd D:\study\get_job_data\backend\orchestration-backend
python app/main.py
```

榛樿鍦板潃锛?
```text
http://127.0.0.1:8091
```

## 甯哥敤鎺ュ彛

### 鑳藉姏灞傜埇铏噰闆?
```http
POST http://127.0.0.1:8090/spider/qcwy/jobs
```

璇ユ帴鍙ｅ彧閲囬泦锛屼笉鍏ュ簱銆?
璇锋眰绀轰緥锛?
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
  "browser_wait_seconds": 25
}
```

### 缂栨帓灞傞噰闆嗗苟鍏ュ簱

```http
POST http://127.0.0.1:8091/job/crawl/qcwy/jobs
```

璇ユ帴鍙ｄ細璋冪敤鑳藉姏灞傜埇铏紝骞舵妸缁撴灉鍐欏叆宀椾綅搴撱€?
璇锋眰绀轰緥锛?
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
  "browser_wait_seconds": 25
}
```

### 鏌ヨ宀椾綅鍒楄〃

```http
POST http://127.0.0.1:8091/job/raw-records/search
```

璇锋眰绀轰緥锛?
```json
{
  "keyword": "AI搴旂敤寮€鍙?,
  "city": "娣卞湷",
  "platform": "qcwy",
  "status": "recruiting",
  "page": 1,
  "page_size": 20
}
```

### 杩愯閫氱敤 Agent

```http
POST http://127.0.0.1:8090/agent/run
```

璇锋眰绀轰緥锛?
```json
{
  "query": "璇锋€荤粨杩欎簺宀椾綅鐨勬妧鑳借姹?,
  "conversation_id": "career-profile-ai-app-dev",
  "system_prompt": "浣犳槸灏变笟鎸囧骞冲彴鐨勫矖浣嶅垎鏋愪笓瀹躲€?,
  "inputs": {},
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

## 鏁版嵁搴撹亴璐?
鑳藉姏灞傦細

- Agent 浼氳瘽銆丄gent 妯℃澘銆丆heckpoint 绛夐€氱敤鑳藉姏鏁版嵁鍙互鐢辫兘鍔涘眰缁存姢銆?- 鐖櫕鑳藉姏涓嶇洿鎺ュ啓宀椾綅涓氬姟琛ㄣ€?
缂栨帓灞傦細

- 璐熻矗宀椾綅涓氬姟琛ㄥ叆搴撱€?- 璐熻矗宀椾綅鍘熷鏁版嵁鍜屾爣鍑嗗矖浣嶆暟鎹淮鎶ゃ€?- 璐熻矗鍚庣画宀椾綅鐢诲儚鐢熸垚缁撴灉鍐欏叆銆?
褰撳墠鏍稿績琛細

```text
spider_crawl_runs
job_raw_records
job_directions
job_market_profiles
agent.agent_conversations
agent.agent_messages
agent.agent_templates
```

## 璁捐鏂囨。

鏍圭洰褰?`docs/` 涓嬪凡缁忔暣鐞嗕簡闃舵鎬ц璁℃枃妗ｏ細

- `鏋舵瀯鍥?md`
- `AC-楠屾敹鏍囧噯鏂囨。.md`
- `TDD-鎶€鏈爣鍑嗘枃妗?md`
- `ERD-鏁版嵁搴撹璁?md`
- `API-SPEC鎺ュ彛鏂囨。.md`

杩欎簺鏂囨。鏄綋鍓嶆灦鏋勫拰鍚庣画寮€鍙戠殑涓昏渚濇嵁銆?
## 鍚庣画瑙勫垝

鐭湡閲嶇偣锛?
- 瀹屽杽宀椾綅閲囬泦鍏ュ簱娴佺▼銆?- 鍩轰簬宀椾綅鏁版嵁鐢熸垚宀椾綅鐢诲儚銆?- 瀹屽杽褰撳墠鍗犱綅鐨勫矖浣嶇敾鍍忕敓鎴愮紪鎺掓帴鍙ｏ細`/job/profiles/generate`銆?
涓湡閲嶇偣锛?
- 缂栨帓灞傛柊澧?`job_profile` 妯″潡銆?- Agent 宸ュ叿鍖栬鍙栧矖浣嶅簱鏁版嵁銆?- 浣跨敤 LangGraph state 鎵胯浇涓棿杩囩▼鏁版嵁銆?
闀挎湡閲嶇偣锛?
- 鑳藉姏灞傛矇娣€涓洪€氱敤 Agent / 鐖櫕 / 妯″瀷鑳藉姏骞冲彴銆?- 缂栨帓灞傛矇娣€灏变笟鎸囧涓氬姟鏅鸿兘娴佺▼銆?- Java 灞傜粺涓€鎵挎帴鏉冮檺銆佺敤鎴枫€侀〉闈㈠拰璋冪敤鍏ュ彛銆?
